import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("mecris.services.reminder")

class ReminderService:
    """Decides when to nudge the user and formats the content for WhatsApp Templates."""

    def __init__(self, context_provider, coaching_provider, log_provider=None):
        self.context_provider = context_provider
        self.coaching_provider = coaching_provider
        self.log_provider = log_provider
        # HX9403f1b85350b8c05780a1128b79f3c2 = mecris_status_v2 (Confirmed working)
        self.walk_template_sid = "HX9403f1b85350b8c05780a1128b79f3c2" 
        self.urgency_template_sid = "HX638b7f9403e04c8fa880370f1b7a9ba1" # urgency_alert_v2

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
        
        if critical_goals:
            # Cooldown: 4 hours for emergencies
            hours_since_emergency = await self._get_hours_since_last("beeminder_emergency", user_id)
            if hours_since_emergency >= 4.0:
                target = critical_goals[0]
                return {
                    "should_send": True,
                    "type": "beeminder_emergency",
                    "template_sid": self.urgency_template_sid,
                    "variables": {
                        "1": target.get("title", target.get("slug")),
                        "2": target.get("runway", "0 days")
                    },
                    "fallback_message": insight.get("message")
                }
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
                    return {
                        "should_send": True,
                        "type": "walk_reminder",
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
                else:
                    return {"should_send": False, "reason": f"Walk reminder on cooldown ({hours_since_walk:.1f}h since last)"}
            elif insight.get("momentum") == "high" and current_hour >= 16:
                # Coaching pivot for high achievers late in the day
                hours_since_coaching = await self._get_hours_since_last("momentum_coaching", user_id)
                if hours_since_coaching >= 12.0: # Once a day max
                    return {
                        "should_send": True,
                        "type": "momentum_coaching",
                        "message": insight.get("message"), # Use freeform for coaching
                        "use_template": False
                    }
                else:
                    return {"should_send": False, "reason": "Coaching pivot already sent today"}

        return {"should_send": False, "reason": "No conditions met for reminder"}
