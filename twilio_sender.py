#!/usr/bin/env python3
"""
Twilio WhatsApp/SMS Sender for Mecris
Integrated messaging for beemergencies and system alerts
"""

import os
import logging
import json
from twilio.rest import Client
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("mecris.twilio")

def send_sms(message: str, to_number: Optional[str] = None) -> bool:
    """Send SMS via Twilio (DISABLED: requires A2P 10DLC registration which is not active)."""
    logger.error("SMS attempted but DISABLED: No A2P campaign active. SMS will fail and incur costs.")
    return False

def send_whatsapp_template(content_sid: str, variables: Dict[str, str], to_number: Optional[str] = None, user_id: Optional[str] = None) -> bool:
    """
    Send a WhatsApp Message Template (Required for starting conversations).
    
    Args:
        content_sid: The Twilio Content SID (starts with HXC...)
        variables: Dictionary of template variables {"1": "65", "2": "Arabic", "3": "Boris & Fiona"}
        to_number: Recipient number
        user_id: User identifier to fetch number from DB
    """
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_WHATSAPP_FROM')
        
        # 1. Resolve to_number from user_id if provided
        final_to = to_number
        if user_id and not final_to:
            from usage_tracker import get_tracker
            user_data = get_tracker().get_user_preferences(user_id)
            enc_phone = user_data.get("phone_number_encrypted")
            if enc_phone:
                try:
                    from services.encryption_service import EncryptionService
                    encryption = EncryptionService()
                    final_to = encryption.decrypt(enc_phone)
                except Exception as e:
                    logger.error(f"Failed to decrypt user phone for {user_id}: {e}")
        
        # 2. Fallback to env
        final_to = final_to or os.getenv('TWILIO_TO_NUMBER')
        
        if not all([account_sid, auth_token, from_number, final_to, content_sid]):
            logger.error("Missing credentials or Content SID for WhatsApp Template")
            return False

        if not final_to.startswith('whatsapp:'):
            final_to = f'whatsapp:{final_to}'

        client = Client(account_sid, auth_token)
        message_obj = client.messages.create(
            from_=from_number,
            to=final_to,
            content_sid=content_sid,
            content_variables=json.dumps(variables)
        )
        logger.info(f"WhatsApp Template sent: {message_obj.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp Template: {e}")
        return False

def send_message(message: str, to_number: Optional[str] = None, user_id: Optional[str] = None) -> bool:
    """Send a freeform WhatsApp message (only works within 24hr window)."""
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
        
        # 1. Resolve to_number from user_id if provided
        final_to = to_number
        if user_id and not final_to:
            from usage_tracker import get_tracker
            user_data = get_tracker().get_user_preferences(user_id)
            enc_phone = user_data.get("phone_number_encrypted")
            if enc_phone:
                try:
                    from services.encryption_service import EncryptionService
                    encryption = EncryptionService()
                    final_to = encryption.decrypt(enc_phone)
                except Exception as e:
                    logger.error(f"Failed to decrypt user phone for {user_id}: {e}")
        
        # 2. Fallback to env
        final_to = final_to or os.getenv('TWILIO_TO_NUMBER')
        
        if not all([account_sid, auth_token, final_to]):
            logger.error("Missing Twilio credentials")
            return False
        
        if not final_to.startswith('whatsapp:'):
            final_to = f'whatsapp:{final_to}'
        
        client = Client(account_sid, auth_token)
        message_obj = client.messages.create(body=message, from_=from_number, to=final_to)
        logger.info(f"WhatsApp message sent: {message_obj.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        return False

def smart_send_message(message: str, to_number: Optional[str] = None, user_id: Optional[str] = None) -> dict:
    """Smart delivery with fallback: Template -> Freeform WhatsApp -> SMS -> Console."""
    delivery_method = os.getenv('REMINDER_DELIVERY_METHOD', 'console').lower()
    content_sid = os.getenv('TWILIO_WHATSAPP_TEMPLATE_SID')
    
    # Check for approved template pool
    approved_pool_path = "data/approved_templates.json"
    if os.path.exists(approved_pool_path):
        try:
            with open(approved_pool_path, 'r') as f:
                pool_data = json.load(f)
                approved_sids = pool_data.get("approved_sids", [])
                if approved_sids:
                    # If current SID not in pool, or no SID set, use first approved
                    if not content_sid or content_sid not in approved_sids:
                        content_sid = approved_sids[0]
                        logger.info(f"Using fallback approved template: {content_sid}")
        except Exception as e:
            logger.warning(f"Failed to load approved template pool: {e}")

    # Check vacation_mode and phone number from DB if user_id provided
    from usage_tracker import get_tracker
    tracker = get_tracker()
    
    # Defaults
    vacation_mode = False
    target_phone = to_number or os.getenv('TWILIO_TO_NUMBER')
    
    if user_id:
        user_data = tracker.get_user_preferences(user_id)
        if user_data:
            # If the phone is encrypted in DB, we need to decrypt it to send
            enc_phone = user_data.get("phone_number_encrypted")
            if enc_phone:
                try:
                    from services.encryption_service import EncryptionService
                    encryption = EncryptionService()
                    target_phone = encryption.decrypt(enc_phone)
                except Exception as e:
                    logger.error(f"Failed to decrypt user phone for {user_id}: {e}")
            
            # Fetch vacation mode from specific field or JSONB prefs
            vacation_mode = user_data.get("notification_prefs", {}).get("vacation_mode", False)
            if not vacation_mode and user_data.get("vacation_mode_until"):
                # If until is in the future, we are in vacation mode
                try:
                    from datetime import datetime, timezone
                    until = user_data["vacation_mode_until"]
                    if isinstance(until, str):
                        until = datetime.fromisoformat(until.replace('Z', '+00:00'))
                    if until > datetime.now(until.tzinfo or timezone.utc):
                        vacation_mode = True
                except: pass

    result = {"sent": False, "method": None, "attempts": []}
    
    # Logic: If we have a template SID and we are doing WhatsApp, try that first
    if delivery_method in ['whatsapp', 'both'] and content_sid:
        # Load template pool to identify mapping
        template_name = "unknown"
        if os.path.exists(approved_pool_path):
            try:
                with open(approved_pool_path, 'r') as f:
                    pool_data = json.load(f)
                    template_name = pool_data.get("approved_templates", {}).get(content_sid, "unknown")
            except: pass

        import re
        
        # Default fallback values
        v1, v2, v3, v4, v5 = "Activity", "Pending", "Commitment", "Due", "???"
        
        # Try to extract values from the message string
        pairs = []
        for line in message.split('\n'):
            line = line.strip()
            if not line or 'System Alert' in line or 'Please log' in line or 'temperature' in line:
                continue
            if ':' in line:
                parts = line.split(':', 1)
                pairs.append((parts[0].strip(), parts[1].strip().rstrip('.')))
        
        if len(pairs) >= 1:
            v1, v2 = pairs[0][0], pairs[0][1]
        if len(pairs) >= 2:
            v3, v4 = pairs[1][0], pairs[1][1]
            
        temp_match = re.search(r"(\d+)F", message)
        if temp_match:
            v5 = temp_match.group(1)
        elif vacation_mode:
            v5 = "Vacation"
        else:
            v5 = "Active"

        # DYNAMIC MAPPING PER TEMPLATE
        if template_name == "mecris_daily_alert_v1":
            # {{1}}: {{4}}, {{2}}: {{5}}, {{3}}F
            variables = {"1": v1, "2": v3, "3": v5, "4": v2, "5": v4}
        elif template_name in ["mecris_status_v2", "mecris_activity_report_v1", "mecris_simple_alert_v1"]:
            # Sequential 1-5 mapping
            # v1=Goal1, v2=Status1, v3=Goal2, v4=Status2, v5=Extra
            mapping_v5 = "daily" if not vacation_mode else "vacation"
            if v5 != "???":
                mapping_v5 = f"{v5}F"
            variables = {"1": v1, "2": v2, "3": v3, "4": v4, "5": mapping_v5}
        else:
            # Fallback to standard 1-5 mapping
            variables = {"1": v1, "2": v2, "3": v3, "4": v4, "5": v5}
        
        success = send_whatsapp_template(content_sid, variables, to_number)
        if success:
            result.update({"sent": True, "method": "whatsapp_template", "template_sid": content_sid})
            return result

    # Fallback to freeform (works if window is open)
    if delivery_method in ['whatsapp', 'both']:
        if send_message(message, to_number):
            result.update({"sent": True, "method": "whatsapp_freeform"})
            return result

    # Final fallback: Console
    print(f"[NARRATOR] {message}")
    result.update({"sent": True, "method": "console"})
    return result

if __name__ == "__main__":
    load_dotenv()
    test_msg = "🧠 Mecris online. System check complete."
    smart_send_message(test_msg)
