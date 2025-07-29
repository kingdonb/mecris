#!/usr/bin/env python3
"""
Twilio WhatsApp Sandbox SMS Sender
Simple function to send messages to Kingdon via WhatsApp sandbox
"""

import os
from twilio.rest import Client
from typing import Optional

def send_message(message: str, to_number: Optional[str] = None) -> bool:
    """
    Send a WhatsApp message via Twilio sandbox
    
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
        from_number = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')  # Default sandbox
        to_number = to_number or os.getenv('TWILIO_TO_NUMBER')
        
        if not all([account_sid, auth_token, to_number]):
            print("Missing Twilio credentials in environment variables")
            return False
        
        # Ensure WhatsApp format
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'
        
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        
        print(f"Message sent: {message.sid}")
        return True
        
    except Exception as e:
        print(f"Failed to send message: {e}")
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

if __name__ == "__main__":
    # Test message
    test_msg = "🧠 Mecris narrator online. Budget tracking active."
    if send_message(test_msg):
        print("Test message sent successfully")
    else:
        print("Test failed - check environment variables")