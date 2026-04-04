import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("mecris.services.reminder")

TIER2_IDLE_HOURS = 6.0  # hours idle before a Tier 1 reminder escalates to Tier 2


class ReminderService:
    """Decides when to nudge the user and formats the content for WhatsApp Templates.

    Core Mandate: 
    - No more than 2 messages per hour across ALL channels.
    - Cooldowns are enforced per-type, but the aggregate frequency is the primary rate-limit.
    """

    def __init__(self, context_provider, coaching_provider, log_provider=None, velocity_provider=None, skip_count_provider=None):
        self.context_provider = context_provider
        self.coaching_provider = coaching_provider
        self.log_provider = log_provider
        self.velocity_provider = velocity_provider
        self.skip_count_provider = skip_count_provider  # async (user_id) -> int: consecutive ignored Arabic cycles
        # HX9403f1b85350b8c05780a1128b79f3c2 = mecris_status_v2 (Confirmed working)
        self.walk_template_sid = "HX9403f1b85350b8c05780a1128b79f3c2" 
        self.urgency_template_sid = "HX638b7f9403e04c8fa880370f1b7a9ba1" # urgency_alert_v2

    def _parse_runway_hours(self, goal: dict) -> float:
        """Return hours of runway from a goal dict.

        Only returns a sub-24h value when the runway string explicitly uses an
        'hours' unit (e.g. '1.5 hours').  Goals expressed in days (e.g. '0 days')
        return 999.0 so they do NOT trigger Tier 3 — 'today' is not the same as
        'within 2 hours'.
        """
        runway = goal.get("runway", "")
        try:
            parts = runway.lower().split()
            if len(parts) >= 2 and "hour" in parts[1]:
                return float(parts[0])
        except (ValueError, IndexError):
            pass
        return 999.0

    async def _get_hours_since_last(self, msg_type: Optional[str] = None, user_id: str = None) -> float:
        """Helper to get hours since a specific message type (or ANY type) was sent."""
        if not self.log_provider:
            return 999.0

        last_sent = await self.log_provider(msg_type, user_id)
        if not last_sent:
            return 999.0

        # Ensure we are comparing aware datetimes if last_sent is aware
        now = datetime.now(timezone.utc) if last_sent.tzinfo else datetime.now()
        diff = now - last_sent
        return diff.total_seconds() / 3600.0


    def _build_tier2_message(self, msg_type: str, hours_idle: float, result: Dict[str, Any]) -> str:
        """Build a contextual escalated message for Tier 2 promotion."""
        hours_str = f"{hours_idle:.0f}h"
        if msg_type == "walk_reminder":
            return (
                f"⚠️ Still no walk after {hours_str}. Boris and Fiona are not impressed. "
                f"This is your escalated reminder — get outside NOW. 🐕🚨"
            )
        if msg_type == "beeminder_emergency":
            goal_title = result.get("variables", {}).get("1", "a Beeminder goal")
            return (
                f"🚨 ESCALATED: '{goal_title}' is still at risk after {hours_str} of silence. "
                f"You've ignored this long enough — address it NOW before it derails. 📉"
            )
        if msg_type == "arabic_review_reminder":
            return (
                f"🚨 Arabic reviews still overdue after {hours_str}. "
                f"reviewstack won't fix itself — open Clozemaster NOW. 📚"
            )
        return (
            f"⚠️ Escalated reminder after {hours_str} idle: this situation hasn't resolved itself. "
            f"Take action NOW. 🔥"
        )

    async def _apply_tier2_escalation(self, result: Dict[str, Any], user_id: str = None) -> Dict[str, Any]:
        """Promote a Tier 1 result to Tier 2 if it has been idle long enough.

        Tier 3 results and already-Tier-2 results are returned unchanged.
        If log_provider is absent or there's no message history, no escalation occurs.
        """
        if result.get("tier") != 1:
            return result
        hours_idle = await self._get_hours_since_last(result["type"], user_id)
        if hours_idle < 999.0 and hours_idle >= TIER2_IDLE_HOURS:
            result = dict(result)
            result["tier"] = 2
            result["use_template"] = False
            result["fallback_message"] = self._build_tier2_message(result["type"], hours_idle, result)
        return result

    def _calculate_dynamic_cooldown(self, base_cooldown: float, current_hour: int) -> float:
        """
        Calculate a dynamic cooldown that gets shorter as the evening progresses,
        with added randomness (fuzz) so it doesn't feel like a rigid formula.
        """
        import random
        reduction = 0.0
        # If it's evening (after 4 PM/16:00), start reducing the cooldown
        if current_hour >= 16:
            # Reduce by 0.15 hours (9 mins) for every hour past 4 PM
            reduction = (current_hour - 16) * 0.15
            
        # Add random fuzz between -0.25 and +0.25 hours (-15 to +15 mins)
        fuzz = random.uniform(-0.25, 0.25)
        
        # Ensure cooldown doesn't drop below 45 minutes
        return max(0.75, base_cooldown - reduction + fuzz)

    async def check_reminder_needed(self, user_id: str = None) -> Dict[str, Any]:
        """Core logic for proactive nudges."""
        # 1. ENFORCE GLOBAL RATE LIMIT: No more than 2 messages per hour (30m cooldown)
        hours_since_any = await self._get_hours_since_last(None, user_id)
        if hours_since_any < 0.5:
            return {
                "should_send": False, 
                "reason": f"Global rate limit: 2x/hour (last sent {hours_since_any*60:.1f}m ago)"
            }

        context = await self.context_provider(user_id)
        insight = await self.coaching_provider(user_id)
        if not isinstance(insight, dict):
            insight = {}
        
        now = datetime.now()
        current_hour = now.hour
        walk_status = context.get("daily_walk_status", {})
        has_walked = walk_status.get("has_activity_today", False)
        vacation_mode = context.get("vacation_mode", False)

        # 1a. ENFORCE SLEEP WINDOWS
        is_normal_sleep_time = current_hour >= 20 or current_hour < 8
        is_emergency_sleep_time = current_hour < 8
        
        # 1. Beeminder Emergencies (Higher Priority, any time)
        beeminder_alerts = context.get("beeminder_alerts", [])
        critical_goals = [g for g in context.get("goal_runway", []) if g.get("derail_risk") == "CRITICAL"]

        # 0. Tier 3: Goal runway expressed in hours and < 2h remaining → WhatsApp High Urgency
        subhour_critical = [g for g in critical_goals if self._parse_runway_hours(g) < 2.0]
        if subhour_critical:
            hours_since_urgent = await self._get_hours_since_last("beeminder_emergency_tier3", user_id)
            if hours_since_urgent >= 1.0:
                target = subhour_critical[0]
                return {
                    "should_send": True,
                    "type": "beeminder_emergency_tier3",
                    "tier": 3,
                    "use_template": False, # Use freeform for maximum flexibility/urgency text
                    "fallback_message": (
                        f"🚨🚨🚨 CRITICAL EMERGENCY: {target.get('title', target.get('slug'))} derails in under 2 hours — TAKE ACTION NOW."
                    )
                }
            else:
                return {"should_send": False, "reason": f"Tier 3 emergency on cooldown ({hours_since_urgent:.1f}h since last)"}

        # EMERGENCIES RESPECT THE EMERGENCY SLEEP WINDOW (12am-8am)
        if not is_emergency_sleep_time:
            is_lever_push = insight.get("type") == "lever_push"
            
            # 1a. Arabic Review Emergency or Lever Push
            arabic_critical = [g for g in critical_goals if g.get("slug") == "reviewstack"]
            
            if arabic_critical or (is_lever_push and insight.get("target_slug") in ["reviewstack", "ellinika"]):
                if self.skip_count_provider and arabic_critical:
                    try:
                        skip_count = await self.skip_count_provider(user_id)
                        if skip_count >= 3:
                            hours_since_escalation = await self._get_hours_since_last("arabic_review_escalation", user_id)
                            if hours_since_escalation >= 1.0:
                                target = arabic_critical[0]
                                return {
                                    "should_send": True,
                                    "type": "arabic_review_escalation",
                                    "tier": 2,
                                    "template_sid": self.urgency_template_sid,
                                    "variables": {
                                        "1": target.get("title", "Arabic Clozemaster"),
                                        "2": target.get("runway", "0 days"),
                                        "3": str(skip_count)
                                    },
                                    "fallback_message": f"🚨🚨 Arabic IGNORED {skip_count}x — OPEN CLOZEMASTER NOW. No excuses."
                                }
                            else:
                                logger.info(f"Arabic escalation suppressed by cooldown ({hours_since_escalation:.1f}h since last)")
                                return {"should_send": False, "reason": f"Arabic escalation on cooldown ({hours_since_escalation:.1f}h since last)"}
                    except Exception:
                        logger.warning("skip_count_provider failed; falling back to arabic_review_reminder")

                dynamic_arabic_cooldown = self._calculate_dynamic_cooldown(2.0, current_hour)
                hours_since_arabic = await self._get_hours_since_last("arabic_review_reminder", user_id)
                
                if hours_since_arabic >= dynamic_arabic_cooldown:
                    target_title = "Language Review"
                    runway = "0 days"
                    if arabic_critical:
                        target_title = arabic_critical[0].get("title", "Arabic Clozemaster")
                        runway = arabic_critical[0].get("runway", "0 days")
                    elif is_lever_push:
                        target_title = insight.get("target_slug", "Language Review")
                    
                    variables = {
                        "1": target_title,
                        "2": runway
                    }
                    if self.velocity_provider:
                        try:
                            velocity = await self.velocity_provider(user_id)
                            arabic_stats = velocity.get("arabic") or velocity.get("Arabic")
                            if arabic_stats and "target_flow_rate" in arabic_stats:
                                variables["3"] = str(arabic_stats["target_flow_rate"])
                        except Exception:
                            logger.warning("velocity_provider failed; omitting cards_needed from arabic reminder")
                            
                    fallback_message = insight.get("message") if is_lever_push else "🚨 Language reviews are CRITICAL — open Clozemaster and do reviews NOW!"
                            
                    result = {
                        "should_send": True,
                        "type": "arabic_review_reminder",
                        "tier": 1,
                        "template_sid": self.urgency_template_sid,
                        "variables": variables,
                        "fallback_message": fallback_message
                    }
                    return await self._apply_tier2_escalation(result, user_id)
                else:
                    logger.info(f"Language reminder suppressed by dynamic cooldown ({hours_since_arabic:.1f}h < {dynamic_arabic_cooldown:.1f}h)")
                    return {"should_send": False, "reason": f"Arabic review reminder on cooldown ({hours_since_arabic:.1f}h since last)"}

            if critical_goals:
                dynamic_emerg_cooldown = self._calculate_dynamic_cooldown(4.0, current_hour)
                hours_since_emergency = await self._get_hours_since_last("beeminder_emergency", user_id)
                if hours_since_emergency >= dynamic_emerg_cooldown:
                    target = critical_goals[0]
                    result = {
                        "should_send": True,
                        "type": "beeminder_emergency",
                        "tier": 1,
                        "template_sid": self.urgency_template_sid,
                        "variables": {
                            "1": target.get("title", target.get("slug")),
                            "2": target.get("runway", "0 days")
                        },
                        "fallback_message": insight.get("message")
                    }
                    return await self._apply_tier2_escalation(result, user_id)
                else:
                    logger.info(f"Emergency reminder suppressed by dynamic cooldown ({hours_since_emergency:.1f}h < {dynamic_emerg_cooldown:.1f}h)")

        # ALL NORMAL REMINDERS RESPECT THE NORMAL SLEEP WINDOW (8pm-8am)
        if is_normal_sleep_time:
            return {"should_send": False, "reason": f"Sleep window active (8pm-8am, current hour: {current_hour})"}
            
        # 2. Walk Reminders (Dynamic window based on user preferences)
        time_window_start = context.get("time_window_start", 13)
        time_window_end = context.get("time_window_end", 17)
        
        if time_window_start <= current_hour <= time_window_end:
            if not has_walked:
                # Cooldown: 2.5 hours between walk nags
                hours_since_walk = await self._get_hours_since_last("walk_reminder", user_id)
                if hours_since_walk >= 2.5:
                    # Format variables for mecris_activity_check_v2
                    result = {
                        "should_send": True,
                        "type": "walk_reminder",
                        "tier": 1,
                        "template_sid": self.walk_template_sid,
                        "variables": {
                            "1": "Daily Walk",
                            "2": "NOT FOUND",
                            "3": "Boris & Fiona" if not vacation_mode else "Personal Activity",
                            "4": "EXPECTANT" if not vacation_mode else "NEEDED",
                            "5": datetime.now().strftime("%I:%M %p")
                        },
                        "fallback_message": insight.get("message")
                    }
                    return await self._apply_tier2_escalation(result, user_id)
                else:
                    return {"should_send": False, "reason": f"Walk reminder on cooldown ({hours_since_walk:.1f}h since last)"}
            elif insight and insight.get("momentum") == "high" and current_hour >= 16:
                # Coaching pivot for high achievers late in the day
                hours_since_coaching = await self._get_hours_since_last("momentum_coaching", user_id)
                if hours_since_coaching >= 12.0: # Once a day max
                    return {
                        "should_send": True,
                        "type": "momentum_coaching",
                        "tier": 2,
                        "message": insight.get("message"), # Use freeform for coaching
                        "use_template": False
                    }
                else:
                    return {"should_send": False, "reason": "Coaching pivot already sent today"}

        return {"should_send": False, "reason": "No conditions met for reminder"}