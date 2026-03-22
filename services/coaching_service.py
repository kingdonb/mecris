from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging
import random

logger = logging.getLogger("mecris.services.coaching")

class InsightType(Enum):
    MOMENTUM_PIVOT = "momentum_pivot"
    URGENCY_ALERT = "urgency_alert"
    WALK_PROMPT = "walk_prompt"
    OBSIDIAN_PIVOT = "obsidian_pivot"
    CELEBRATION = "celebration"
    LEVER_PUSH = "lever_push"

@dataclass
class CoachingInsight:
    type: InsightType
    momentum: str  # "high", "low", "neutral"
    message: str
    target_slug: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "momentum": self.momentum,
            "message": self.message,
            "target_slug": self.target_slug
        }

class CoachingService:
    def __init__(self, context_provider, goal_provider, obsidian_provider):
        self.context_provider = context_provider
        self.goal_provider = goal_provider
        self.obsidian_provider = obsidian_provider

    async def generate_insight(self) -> CoachingInsight:
        """Generate a personalized coaching insight based on context."""
        try:
            context = await self.context_provider()
            walk_status = context.get("daily_walk_status", {})
            has_walked = walk_status.get("has_activity_today", False)
            vacation_mode = context.get("vacation_mode", False)
            
            beeminder_goals = await self.goal_provider()
            warning_goals = [g for g in beeminder_goals if g.get("derail_risk") in ["WARNING", "CAUTION"]]
            critical_goals = [g for g in beeminder_goals if g.get("derail_risk") == "CRITICAL"]
            
            # Fetch Language Stats for Lever Awareness
            from services.neon_sync_checker import NeonSyncChecker
            neon = NeonSyncChecker()
            lang_stats = neon.get_language_stats()
            
            # Priority 1: High Pressure Arabic (Lever Aware)
            arabic = lang_stats.get("ARABIC", {})
            if arabic.get("current", 0) > 0 and arabic.get("multiplier", 1.0) >= 3.0:
                return self._handle_arabic_pressure(arabic)

            # Priority 2: High Momentum (Already walked/active)
            if has_walked:
                return await self._handle_high_momentum(critical_goals, warning_goals, vacation_mode, lang_stats)
            
            # Priority 3: Low Momentum (Needs activity)
            return self._handle_low_momentum(critical_goals, vacation_mode)
            
        except Exception as e:
            logger.error(f"Error generating coaching insight: {e}")
            raise

    def _handle_arabic_pressure(self, arabic: Dict) -> CoachingInsight:
        multiplier = arabic.get("multiplier", 1.0)
        debt = arabic.get("current", 0)
        
        messages = [
            f"📈 You've got the Arabic lever set to {multiplier}x. That's a lot of talk for someone with {debt} reviews due. Log in and clear it. 😤",
            f"💀 {debt} Arabic cards are waiting. You set the pressure to {multiplier}x yourself. Don't make me remind you again. 🔪",
            f"⚖️ Arabic Debt: {debt}. Lever: {multiplier}x. The math doesn't add up until you do the work. Move it! 🏃‍♂️"
        ]
        
        return CoachingInsight(
            type=InsightType.LEVER_PUSH,
            momentum="low",
            message=random.choice(messages),
            target_slug="reviewstack"
        )

    async def _handle_high_momentum(self, critical: List[Dict], warning: List[Dict], vacation_mode: bool, lang_stats: Dict) -> CoachingInsight:
        # Check Greek "PLAY" Driver
        greek = lang_stats.get("GREEK", {})
        if greek.get("current", 0) < 50 and greek.get("multiplier", 1.0) >= 2.0:
            return CoachingInsight(
                type=InsightType.LEVER_PUSH,
                momentum="high",
                message=f"🇬🇷 You're active and Greek is looking too safe (only {greek.get('current')} reviews). Time to PLAY some new cards and build that backlog! ⚡",
                target_slug="ellinika"
            )

        if critical:
            target = critical[0]
            success_msg = "Great job on the walk!" if not vacation_mode else "Nice work staying active!"
            return CoachingInsight(
                type=InsightType.MOMENTUM_PIVOT,
                momentum="high",
                message=f"🌟 {success_msg} Since you're on a roll, let's tackle the critical '{target['title']}' goal next. 🚀",
                target_slug=target["slug"]
            )
        
        if warning:
            target = warning[0]
            success_msg = "the walk" if not vacation_mode else "hitting your activity goal"
            return CoachingInsight(
                type=InsightType.MOMENTUM_PIVOT,
                momentum="high",
                message=f"🔥 Solid work {success_msg}! Ready to keep the streak going with some progress on '{target['title']}'? 📚",
                target_slug=target["slug"]
            )
            
        # Check Obsidian Context
        try:
            today_note = await self.obsidian_provider()
            if today_note and "Mecris" in today_note:
                return CoachingInsight(
                    type=InsightType.OBSIDIAN_PIVOT,
                    momentum="high",
                    message="🏗️ You've been crushing it on the Mecris architecture today and you've already logged activity. Keep that momentum! 🚀"
                )
        except Exception as e:
            logger.warning(f"Failed to fetch obsidian context: {e}")

        return CoachingInsight(
            type=InsightType.CELEBRATION,
            momentum="high",
            message="🌈 You're all caught up and you've already logged activity! Enjoy the headspace for some creative work. ✨"
        )

    def _handle_low_momentum(self, critical: List[Dict], vacation_mode: bool) -> CoachingInsight:
        if critical:
            target = critical[0]
            walk_msg = "A quick walk" if not vacation_mode else "A quick personal activity"
            return CoachingInsight(
                type=InsightType.URGENCY_ALERT,
                momentum="low",
                message=f"⚠️ Heads up! '{target['title']}' is critical. {walk_msg} might be the reset you need to dive in. 🐕",
                target_slug=target["slug"]
            )
        
        if vacation_mode:
            return CoachingInsight(
                type=InsightType.WALK_PROMPT,
                momentum="neutral",
                message="🏃 Time for a quick activity! A few minutes of movement will set a great tone for the day. 🌳"
            )

        return CoachingInsight(
            type=InsightType.WALK_PROMPT,
            momentum="neutral",
            message="🐕 Boris and Fiona are ready when you are. A walk now will set a great tone for the rest of your goals! 🌳"
        )
