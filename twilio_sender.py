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
    
    result = {"sent": False, "method": None, "attempts": []}
    
    # Logic: If we have a template SID and we are doing WhatsApp, try that first
    if delivery_method in ['whatsapp', 'both'] and content_sid:
        # Example variables mapping for your new template
        # 1=temp, 2=goal, 3=doggies
        # For generic messages, we might just put the whole message in variable 1
        # but for now we'll just try to send it simply.
        variables = {"1": "??", "2": "Accountability", "3": "Doggies"} 
        if "weather" in message.lower():
             # Crude extraction for testing - in production we'd pass structured data
             variables["1"] = "65" 
        
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
