#!/usr/bin/env python3
"""
Twilio WhatsApp/SMS Sender for Mecris
Integrated messaging for beemergencies and system alerts
"""

import os
import logging
from twilio.rest import Client
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("mecris.twilio")

def send_sms(message: str, to_number: Optional[str] = None) -> bool:
    """
    Send SMS via Twilio (preferred method for beemergencies)
    
    Args:
        message: Text to send
        to_number: Recipient number (defaults to env var)
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Twilio credentials from environment
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_FROM_NUMBER')
        to_number = to_number or os.getenv('TWILIO_TO_NUMBER')
        
        if not all([account_sid, auth_token, from_number, to_number]):
            logger.error("Missing Twilio credentials in environment variables")
            return False
        
        client = Client(account_sid, auth_token)
        
        message_obj = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        
        logger.info(f"SMS sent: {message_obj.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        return False

def send_message(message: str, to_number: Optional[str] = None, delivery_method: Optional[str] = None) -> bool:
    """
    Send a WhatsApp message via Twilio sandbox
    
    Args:
        message: Text to send
        to_number: Recipient number (defaults to env var)
        delivery_method: Override delivery method from env
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Twilio credentials from environment
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')  # Default sandbox
        to_number = to_number or os.getenv('TWILIO_TO_NUMBER')
        
        if not all([account_sid, auth_token, to_number]):
            logger.error("Missing Twilio credentials in environment variables")
            return False
        
        # Ensure WhatsApp format
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'
        
        client = Client(account_sid, auth_token)
        
        message_obj = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        
        logger.info(f"WhatsApp message sent: {message_obj.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        return False

def budget_alert(credits_remaining: float, daily_burn: float) -> None:
    """Send a budget warning message"""
    days_left = credits_remaining / daily_burn if daily_burn > 0 else float('inf')
    
    if days_left < 2:
        urgency = "🚨 CRITICAL"
    elif days_left < 5:
        urgency = "⚠️ WARNING"
    else:
        return  # Don't spam if we're fine
    
    message = f"""{urgency}: Claude Credits Low

${credits_remaining:.2f} remaining
${daily_burn:.2f}/day burn rate
~{days_left:.1f} days left

Time to wrap up or top up."""
    
    send_message(message)

def smart_send_message(message: str, to_number: Optional[str] = None) -> dict:
    """
    Smart message delivery with configurable methods and fallbacks
    
    Returns:
        dict with delivery status, method used, and any errors
    """
    # Get delivery configuration
    delivery_method = os.getenv('REMINDER_DELIVERY_METHOD', 'console').lower()
    enable_fallback = os.getenv('REMINDER_ENABLE_FALLBACK', 'true').lower() == 'true'
    test_mode = os.getenv('REMINDER_TEST_MODE', 'false').lower() == 'true'
    
    result = {
        "sent": False,
        "method": None,
        "message": message,
        "test_mode": test_mode,
        "attempts": []
    }
    
    # Test mode - just log to console
    if test_mode:
        print(f"[TEST MODE] Would send message: {message}")
        logger.info(f"Test mode message: {message}")
        result["sent"] = True
        result["method"] = "test_console"
        return result
    
    # Console delivery
    if delivery_method == 'console':
        print(f"[REMINDER] {message}")
        logger.info(f"Console reminder: {message}")
        result["sent"] = True
        result["method"] = "console"
        return result
    
    # Try delivery methods based on configuration
    methods_to_try = []
    
    if delivery_method == 'sms':
        methods_to_try = ['sms']
    elif delivery_method == 'whatsapp':
        methods_to_try = ['whatsapp']
    elif delivery_method == 'both':
        methods_to_try = ['whatsapp', 'sms']  # WhatsApp first, SMS fallback
    else:
        # Default fallback to console if method not recognized
        print(f"[REMINDER] {message}")
        logger.info(f"Console reminder (unknown method '{delivery_method}'): {message}")
        result["sent"] = True
        result["method"] = "console_fallback"
        return result
    
    # Add fallback methods if enabled
    if enable_fallback:
        if 'whatsapp' not in methods_to_try:
            methods_to_try.append('whatsapp')
        if 'sms' not in methods_to_try:
            methods_to_try.append('sms')
        # Console as final fallback
        methods_to_try.append('console')
    
    # Try each method in order
    for method in methods_to_try:
        attempt = {"method": method, "success": False, "error": None}
        
        try:
            if method == 'sms':
                success = send_sms(message, to_number)
                attempt["success"] = success
                if success:
                    result["sent"] = True
                    result["method"] = "sms"
                    result["attempts"].append(attempt)
                    return result
                else:
                    attempt["error"] = "SMS delivery failed"
                    
            elif method == 'whatsapp':
                success = send_message(message, to_number)
                attempt["success"] = success
                if success:
                    result["sent"] = True
                    result["method"] = "whatsapp"
                    result["attempts"].append(attempt)
                    return result
                else:
                    attempt["error"] = "WhatsApp delivery failed"
                    
            elif method == 'console':
                print(f"[FALLBACK REMINDER] {message}")
                logger.info(f"Fallback console reminder: {message}")
                attempt["success"] = True
                result["sent"] = True
                result["method"] = "console_fallback"
                result["attempts"].append(attempt)
                return result
                
        except Exception as e:
            attempt["error"] = str(e)
            logger.error(f"Error attempting {method} delivery: {e}")
        
        result["attempts"].append(attempt)
    
    # If we get here, all methods failed
    logger.error(f"All delivery methods failed for message: {message}")
    return result

if __name__ == "__main__":
    # Test message
    test_msg = "🧠 Mecris narrator online. Budget tracking active."
    if send_message(test_msg):
        print("Test message sent successfully")
    else:
        print("Test failed - check environment variables")