import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("mecris.services.reminder")

class ReminderService:
    """Decides when to nudge the user and formats the content for WhatsApp Templates."""

    def __init__(self, context_provider, coaching_provider):
        self.context_provider = context_provider
        self.coaching_provider = coaching_provider
        # HX9403f1b85350b8c05780a1128b79f3c2 = mecris_status_v2 (Confirmed working)
        self.walk_template_sid = "HX9403f1b85350b8c05780a1128b79f3c2" 
        self.urgency_template_sid = "HX638b7f9403e04c8fa880370f1b7a9ba1" # urgency_alert_v2

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

        # 2. Walk Reminders (Afternoon window: 1 PM - 5 PM)
        if 13 <= current_hour <= 17:
            if not has_walked:
                # Format variables for mecris_activity_check_v2
                # {{1}} = Record Name, {{2}} = Status, {{3}} = Entity, {{4}} = Entity Status, {{5}} = Time
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
            elif insight.get("momentum") == "high" and current_hour >= 16:
                # Coaching pivot for high achievers late in the day
                return {
                    "should_send": True,
                    "type": "momentum_coaching",
                    "message": insight.get("message"), # Use freeform for coaching
                    "use_template": False
                }

        return {"should_send": False, "reason": "No conditions met for reminder"}
