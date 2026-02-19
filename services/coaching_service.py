from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger("mecris.services.coaching")

class InsightType(Enum):
    MOMENTUM_PIVOT = "momentum_pivot"
    URGENCY_ALERT = "urgency_alert"
    WALK_PROMPT = "walk_prompt"
    OBSIDIAN_PIVOT = "obsidian_pivot"
    CELEBRATION = "celebration"

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
            
            beeminder_goals = await self.goal_provider()
            warning_goals = [g for g in beeminder_goals if g.get("derail_risk") in ["WARNING", "CAUTION"]]
            critical_goals = [g for g in beeminder_goals if g.get("derail_risk") == "CRITICAL"]
            
            # Priority 1: High Momentum (Already walked)
            if has_walked:
                return await self._handle_high_momentum(critical_goals, warning_goals)
            
            # Priority 2: Low Momentum (Needs walk)
            return self._handle_low_momentum(critical_goals)
            
        except Exception as e:
            logger.error(f"Error generating coaching insight: {e}")
            raise

    async def _handle_high_momentum(self, critical: List[Dict], warning: List[Dict]) -> CoachingInsight:
        if critical:
            target = critical[0]
            return CoachingInsight(
                type=InsightType.MOMENTUM_PIVOT,
                momentum="high",
                message=f"🌟 Great job on the walk! Since you're on a roll, let's tackle the critical '{target['title']}' goal next. 🚀",
                target_slug=target["slug"]
            )
        
        if warning:
            target = warning[0]
            return CoachingInsight(
                type=InsightType.MOMENTUM_PIVOT,
                momentum="high",
                message=f"🔥 Solid work walking Boris and Fiona! Ready to keep the streak going with some progress on '{target['title']}'? 📚",
                target_slug=target["slug"]
            )
            
        # Check Obsidian Context
        try:
            today_note = await self.obsidian_provider()
            if today_note and "Mecris" in today_note:
                return CoachingInsight(
                    type=InsightType.OBSIDIAN_PIVOT,
                    momentum="high",
                    message="🏗️ You've been crushing it on the Mecris architecture today and you've already walked. Keep that momentum! 🚀"
                )
        except Exception as e:
            logger.warning(f"Failed to fetch obsidian context: {e}")

        return CoachingInsight(
            type=InsightType.CELEBRATION,
            momentum="high",
            message="🌈 You're all caught up and you've already walked! Enjoy the headspace for some creative work. ✨"
        )

    def _handle_low_momentum(self, critical: List[Dict]) -> CoachingInsight:
        if critical:
            target = critical[0]
            return CoachingInsight(
                type=InsightType.URGENCY_ALERT,
                momentum="low",
                message=f"⚠️ Heads up! '{target['title']}' is critical. A quick walk with Boris and Fiona might be the reset you need to dive in. 🐕",
                target_slug=target["slug"]
            )
        
        return CoachingInsight(
            type=InsightType.WALK_PROMPT,
            momentum="neutral",
            message="🐕 Boris and Fiona are ready when you are. A walk now will set a great tone for the rest of your goals! 🌳"
        )
