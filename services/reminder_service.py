import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("mecris.services.reminder")

TIER2_IDLE_HOURS = 6.0  # hours idle before a Tier 1 reminder escalates to Tier 2


class ReminderService:
    """Decides when to nudge the user and formats the content for WhatsApp Templates."""

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

    async def _get_hours_since_last(self, msg_type: str, user_id: str = None) -> float:
        """Helper to get hours since a specific message type was sent."""
        if not self.log_provider:
            return 999.0 # If no provider, assume it's been a long time
        
        last_sent = await self.log_provider(msg_type, user_id)
        if not last_sent:
            return 999.0
            
        # Ensure we are comparing aware datetimes if last_sent is aware
        now = datetime.now(timezone.utc) if last_sent.tzinfo else datetime.now()
        diff = now - last_sent
        return diff.total_seconds() / 3600.0

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
        return result

    async def check_reminder_needed(self, user_id: str = None) -> Dict[str, Any]:
        """Core logic for proactive nudges."""
        context = await self.context_provider(user_id)
        insight = await self.coaching_provider(user_id)
        
        current_hour = datetime.now().hour
        walk_status = context.get("daily_walk_status", {})
        has_walked = walk_status.get("has_activity_today", False)
        vacation_mode = context.get("vacation_mode", False)
        
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

        # 1a. Arabic Review Emergency (obnoxious — 2h cooldown, fires before generic)
        arabic_critical = [g for g in critical_goals if g.get("slug") == "reviewstack"]
        if arabic_critical:
            # Phase 3: escalation ladder — if ignored 3+ consecutive cycles, use more aggressive reminder
            if self.skip_count_provider:
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

            hours_since_arabic = await self._get_hours_since_last("arabic_review_reminder", user_id)
            if hours_since_arabic >= 2.0:
                target = arabic_critical[0]
                variables = {
                    "1": target.get("title", "Arabic Clozemaster"),
                    "2": target.get("runway", "0 days")
                }
                if self.velocity_provider:
                    try:
                        velocity = await self.velocity_provider(user_id)
                        arabic_stats = velocity.get("arabic") or velocity.get("Arabic")
                        if arabic_stats and "target_flow_rate" in arabic_stats:
                            variables["3"] = str(arabic_stats["target_flow_rate"])
                    except Exception:
                        logger.warning("velocity_provider failed; omitting cards_needed from arabic reminder")
                result = {
                    "should_send": True,
                    "type": "arabic_review_reminder",
                    "tier": 1,
                    "template_sid": self.urgency_template_sid,
                    "variables": variables,
                    "fallback_message": "🚨 Arabic reviewstack is CRITICAL — open Clozemaster and do reviews NOW!"
                }
                return await self._apply_tier2_escalation(result, user_id)
            else:
                logger.info(f"Arabic reminder suppressed by cooldown ({hours_since_arabic:.1f}h since last)")
                return {"should_send": False, "reason": f"Arabic review reminder on cooldown ({hours_since_arabic:.1f}h since last)"}

        if critical_goals:
            # Cooldown: 4 hours for emergencies
            hours_since_emergency = await self._get_hours_since_last("beeminder_emergency", user_id)
            if hours_since_emergency >= 4.0:
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
                logger.info(f"Emergency reminder suppressed by cooldown ({hours_since_emergency:.1f}h since last)")

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
            elif insight.get("momentum") == "high" and current_hour >= 16:
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
