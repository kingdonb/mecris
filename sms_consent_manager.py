#!/usr/bin/env python3
"""
SMS Consent Manager for Mecris A2P Compliance
Handles opt-in, opt-out, and preference management
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("mecris.consent")

class SMSConsentManager:
    """Manages SMS consent and preferences for A2P compliance"""
    
    def __init__(self, data_file: str = "data/sms_consent.json"):
        self.data_file = Path(data_file)
        self.data_file.parent.mkdir(exist_ok=True)
        self.consent_data = self._load_consent_data()
    
    def _load_consent_data(self) -> Dict:
        """Load consent data from file"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load consent data: {e}")
        
        # Default structure
        return {
            "users": {},
            "global_settings": {
                "created": datetime.now().isoformat(),
                "version": "1.0"
            }
        }
    
    def _save_consent_data(self):
        """Save consent data to file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.consent_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save consent data: {e}")
    
    def opt_in_user(self, phone_number: str, consent_method: str = "web", 
                   message_types: List[str] = None) -> Dict:
        """
        Record user opt-in for SMS messages
        
        Args:
            phone_number: User's phone number
            consent_method: How they opted in (web, sms, api)
            message_types: Types of messages they want to receive
        """
        if message_types is None:
            message_types = ["walk_reminder", "budget_alert", "beeminder_emergency"]
        
        user_id = phone_number.replace('+', '').replace('-', '').replace(' ', '')
        
        consent_record = {
            "phone_number": phone_number,
            "opted_in": True,
            "opt_in_date": datetime.now().isoformat(),
            "opt_in_method": consent_method,
            "message_types": message_types,
            "preferences": {
                "time_window_start": 14,  # 2 PM
                "time_window_end": 17,    # 5 PM
                "max_messages_per_day": 3,
                "enabled_days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            },
            "message_history": [],
            "last_updated": datetime.now().isoformat()
        }
        
        self.consent_data["users"][user_id] = consent_record
        self._save_consent_data()
        
        logger.info(f"User {phone_number} opted in via {consent_method}")
        return consent_record
    
    def opt_out_user(self, phone_number: str, method: str = "sms") -> bool:
        """
        Record user opt-out
        
        Args:
            phone_number: User's phone number
            method: How they opted out (sms, web, support)
        """
        user_id = phone_number.replace('+', '').replace('-', '').replace(' ', '')
        
        if user_id in self.consent_data["users"]:
            self.consent_data["users"][user_id]["opted_in"] = False
            self.consent_data["users"][user_id]["opt_out_date"] = datetime.now().isoformat()
            self.consent_data["users"][user_id]["opt_out_method"] = method
            self.consent_data["users"][user_id]["last_updated"] = datetime.now().isoformat()
            
            self._save_consent_data()
            logger.info(f"User {phone_number} opted out via {method}")
            return True
        
        logger.warning(f"Attempted to opt out unknown user: {phone_number}")
        return False
    
    def can_send_message(self, phone_number: str, message_type: str = "walk_reminder") -> Dict:
        """
        Check if we can send a message to this user
        
        Returns:
            dict with can_send boolean and reason
        """
        user_id = phone_number.replace('+', '').replace('-', '').replace(' ', '')
        
        if user_id not in self.consent_data["users"]:
            return {"can_send": False, "reason": "User not found in consent database"}
        
        user = self.consent_data["users"][user_id]
        
        if not user.get("opted_in", False):
            return {"can_send": False, "reason": "User has opted out"}
        
        if message_type not in user.get("message_types", []):
            return {"can_send": False, "reason": f"User not consented for message type: {message_type}"}
        
        # Check daily message limit
        today = datetime.now().date().isoformat()
        today_messages = [msg for msg in user.get("message_history", []) 
                         if msg.get("date", "").startswith(today)]
        
        max_per_day = user.get("preferences", {}).get("max_messages_per_day", 3)
        if len(today_messages) >= max_per_day:
            return {"can_send": False, "reason": f"Daily message limit reached ({max_per_day})"}
        
        # Check time window
        current_hour = datetime.now().hour
        start_hour = user.get("preferences", {}).get("time_window_start", 14)
        end_hour = user.get("preferences", {}).get("time_window_end", 17)
        
        if not (start_hour <= current_hour <= end_hour):
            return {"can_send": False, "reason": f"Outside user's time window ({start_hour}-{end_hour})"}
        
        return {"can_send": True, "reason": "All consent checks passed"}
    
    def log_message_sent(self, phone_number: str, message: str, message_type: str, 
                        delivery_method: str = "sms") -> bool:
        """Log that a message was sent to maintain audit trail"""
        user_id = phone_number.replace('+', '').replace('-', '').replace(' ', '')
        
        if user_id not in self.consent_data["users"]:
            logger.error(f"Cannot log message for unknown user: {phone_number}")
            return False
        
        message_record = {
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().date().isoformat(),
            "message": message,
            "message_type": message_type,
            "delivery_method": delivery_method
        }
        
        self.consent_data["users"][user_id]["message_history"].append(message_record)
        
        # Keep only last 30 days of history
        cutoff_date = (datetime.now().date() - timedelta(days=30)).isoformat()
        self.consent_data["users"][user_id]["message_history"] = [
            msg for msg in self.consent_data["users"][user_id]["message_history"]
            if msg.get("date", "9999-12-31") >= cutoff_date
        ]
        
        self._save_consent_data()
        return True
    
    def get_user_preferences(self, phone_number: str) -> Optional[Dict]:
        """Get user's current preferences"""
        user_id = phone_number.replace('+', '').replace('-', '').replace(' ', '')
        return self.consent_data["users"].get(user_id)
    
    def update_user_preferences(self, phone_number: str, preferences: Dict) -> bool:
        """Update user's messaging preferences"""
        user_id = phone_number.replace('+', '').replace('-', '').replace(' ', '')
        
        if user_id not in self.consent_data["users"]:
            return False
        
        # Update preferences while preserving consent status
        current_prefs = self.consent_data["users"][user_id].get("preferences", {})
        current_prefs.update(preferences)
        self.consent_data["users"][user_id]["preferences"] = current_prefs
        self.consent_data["users"][user_id]["last_updated"] = datetime.now().isoformat()
        
        self._save_consent_data()
        return True
    
    def get_consent_summary(self) -> Dict:
        """Get summary of all consent data for monitoring"""
        users = self.consent_data["users"]
        
        opted_in = len([u for u in users.values() if u.get("opted_in", False)])
        opted_out = len([u for u in users.values() if not u.get("opted_in", False)])
        
        return {
            "total_users": len(users),
            "opted_in": opted_in,
            "opted_out": opted_out,
            "message_types_breakdown": self._get_message_type_breakdown(),
            "recent_activity": self._get_recent_activity()
        }
    
    def _get_message_type_breakdown(self) -> Dict:
        """Get breakdown of message type preferences"""
        breakdown = {}
        for user in self.consent_data["users"].values():
            if user.get("opted_in", False):
                for msg_type in user.get("message_types", []):
                    breakdown[msg_type] = breakdown.get(msg_type, 0) + 1
        return breakdown
    
    def _get_recent_activity(self) -> List:
        """Get recent opt-in/opt-out activity"""
        activity = []
        for user in self.consent_data["users"].values():
            if user.get("opt_in_date"):
                activity.append({
                    "action": "opt_in",
                    "date": user["opt_in_date"],
                    "phone": user["phone_number"][-4:]  # Only last 4 digits for privacy
                })
            if user.get("opt_out_date"):
                activity.append({
                    "action": "opt_out", 
                    "date": user["opt_out_date"],
                    "phone": user["phone_number"][-4:]
                })
        
        # Sort by date, most recent first
        activity.sort(key=lambda x: x["date"], reverse=True)
        return activity[:10]  # Return last 10 activities

# Global instance for easy import
consent_manager = SMSConsentManager()

if __name__ == "__main__":
    # Test the consent system
    print("🧠 Mecris SMS Consent Manager Test")
    
    # Test opt-in
    test_phone = "+1234567890"
    consent_manager.opt_in_user(test_phone, "test", ["walk_reminder", "budget_alert"])
    
    # Test permission check
    result = consent_manager.can_send_message(test_phone, "walk_reminder")
    print(f"Can send walk reminder: {result}")
    
    # Test message logging
    consent_manager.log_message_sent(test_phone, "Test walk reminder", "walk_reminder", "console")
    
    # Test summary
    summary = consent_manager.get_consent_summary()
    print(f"Consent summary: {summary}")
    
    print("✅ Consent system test complete")