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
    """Send SMS via Twilio (requires A2P 10DLC registration for US)."""
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_FROM_NUMBER')
        to_number = to_number or os.getenv('TWILIO_TO_NUMBER')
        
        if not all([account_sid, auth_token, from_number, to_number]):
            logger.error("Missing Twilio credentials in environment variables")
            return False
        
        client = Client(account_sid, auth_token)
        message_obj = client.messages.create(body=message, from_=from_number, to=to_number)
        logger.info(f"SMS sent: {message_obj.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        return False

def send_whatsapp_template(content_sid: str, variables: Dict[str, str], to_number: Optional[str] = None) -> bool:
    """
    Send a WhatsApp Message Template (Required for starting conversations).
    
    Args:
        content_sid: The Twilio Content SID (starts with HXC...)
        variables: Dictionary of template variables {"1": "65", "2": "Arabic", "3": "Boris & Fiona"}
        to_number: Recipient number
    """
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_WHATSAPP_FROM')
        to_number = to_number or os.getenv('TWILIO_TO_NUMBER')
        
        if not all([account_sid, auth_token, from_number, to_number, content_sid]):
            logger.error("Missing credentials or Content SID for WhatsApp Template")
            return False

        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'

        client = Client(account_sid, auth_token)
        message_obj = client.messages.create(
            from_=from_number,
            to=to_number,
            content_sid=content_sid,
            content_variables=json.dumps(variables)
        )
        logger.info(f"WhatsApp Template sent: {message_obj.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp Template: {e}")
        return False

def send_message(message: str, to_number: Optional[str] = None) -> bool:
    """Send a freeform WhatsApp message (only works within 24hr window)."""
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
        to_number = to_number or os.getenv('TWILIO_TO_NUMBER')
        
        if not all([account_sid, auth_token, to_number]):
            logger.error("Missing Twilio credentials")
            return False
        
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'
        
        client = Client(account_sid, auth_token)
        message_obj = client.messages.create(body=message, from_=from_number, to=to_number)
        logger.info(f"WhatsApp message sent: {message_obj.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        return False

def smart_send_message(message: str, to_number: Optional[str] = None) -> dict:
    """Smart delivery with fallback: Template -> Freeform WhatsApp -> SMS -> Console."""
    delivery_method = os.getenv('REMINDER_DELIVERY_METHOD', 'console').lower()
    content_sid = os.getenv('TWILIO_WHATSAPP_TEMPLATE_SID')
    
    # Check vacation_mode to determine generic vs doggie labels
    from sms_consent_manager import consent_manager
    vacation_mode = False
    target_phone = to_number or os.getenv('TWILIO_TO_NUMBER')
    if target_phone:
        user_prefs = consent_manager.get_user_preferences(target_phone)
        if user_prefs:
            vacation_mode = user_prefs.get("preferences", {}).get("vacation_mode", False)

    result = {"sent": False, "method": None, "attempts": []}
    
    # Logic: If we have a template SID and we are doing WhatsApp, try that first
    if delivery_method in ['whatsapp', 'both'] and content_sid:
        # Variables mapping for mecris_daily_alert_v1:
        # {{1}}: {{2}}
        # {{3}}: {{4}}
        # Current local temperature: {{5}}F
        
        import re
        
        # Default fallback values
        v1, v2, v3, v4, v5 = "Activity", "Pending", "Commitment", "Due", "???"
        
        # Try to extract values from the message string
        # Look for lines that look like "Label: Value"
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
            
        # Pattern 2: Temperature
        temp_match = re.search(r"(\d+)F", message)
        if temp_match:
            v5 = temp_match.group(1)
        elif vacation_mode:
            v5 = "Vacation"
        else:
            v5 = "Active"

        variables = {
            "1": v1,
            "2": v2,
            "3": v3,
            "4": v4,
            "5": v5
        }
        
        success = send_whatsapp_template(content_sid, variables, to_number)
        if success:
            result.update({"sent": True, "method": "whatsapp_template"})
            return result

    # Fallback to freeform (works if window is open)
    if delivery_method in ['whatsapp', 'both']:
        if send_message(message, to_number):
            result.update({"sent": True, "method": "whatsapp_freeform"})
            return result

    # Fallback to SMS
    if delivery_method in ['sms', 'both']:
        if send_sms(message, to_number):
            result.update({"sent": True, "method": "sms"})
            return result

    # Final fallback: Console
    print(f"[NARRATOR] {message}")
    result.update({"sent": True, "method": "console"})
    return result

if __name__ == "__main__":
    load_dotenv()
    test_msg = "🧠 Mecris online. System check complete."
    smart_send_message(test_msg)
