#!/usr/bin/env python3
"""
Base Mode Walk Reminder
A zero-cost, compliance-aware script to remind the user to walk the dogs.
Uses the SMS Consent Manager and Twilio sender, gracefully degrading
when Claude credits are $0 or the main server is down.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from twilio_sender import smart_send_message
import asyncio
from beeminder_client import BeeminderClient

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mecris.base_reminder")

def check_walk_needed() -> bool:
    """Check if the 'bike' goal (dog walk proxy) has activity today."""
    try:
        client = BeeminderClient()
        # has_activity_today returns True if there is activity, so we need a walk if it returns False
        has_activity = asyncio.run(client.has_activity_today("bike"))
        if has_activity:
            logger.info("Walk already logged today.")
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking walk status: {e}")
        # Fail safe: assume needed if we can't check
        return True

def run_base_reminder():
    load_dotenv()
    
    # Target phone number
    target_phone = os.getenv('TWILIO_TO_NUMBER')
    if not target_phone:
        logger.error("TWILIO_TO_NUMBER environment variable not set.")
        return

    # 1. Check if walk is needed
    logger.info("Checking if dogs have been walked...")
    if not check_walk_needed():
        logger.info("Dogs already walked. No reminder needed.")
        return
        
    # 2. Check Consent and Compliance Window
    logger.info(f"Checking consent for {target_phone}...")

    from usage_tracker import get_tracker
    tracker = get_tracker()
    user_prefs = tracker.get_user_preferences() # Default user

    # If user not in DB, we can't really "auto-enroll" here anymore without a pocket_id
    if not user_prefs:
        logger.error("User not found in Neon database. Please run OIDC bootstrap.")
        return

    # Use notification_prefs from DB
    prefs = user_prefs.get("notification_prefs", {})
    vacation_mode = prefs.get("vacation_mode", False)

    # Compliance check (ported from manager logic)
    if not prefs.get("sms_opted_in", False):
        logger.info("Compliance check failed: User not opted in for SMS")
        return

    current_hour = datetime.now().hour
    start_hour = prefs.get("time_window_start", 14)
    end_hour = prefs.get("time_window_end", 17)

    if not (start_hour <= current_hour <= end_hour):
        logger.info(f"Compliance check failed: Outside user's time window ({start_hour}-{end_hour})")
        return

    # 3. Send hard-coded zero-token message matching the approved WhatsApp template exactly    # Template:
    # Mecris System Alert: This is your daily activity update.
    # {{1}}: {{4}}.
    # {{2}}: {{5}}.
    # Current local temperature: {{3}}F.
    # Please log your activity to maintain your account standing.
    
    if vacation_mode:
        walk_line = "Activity log: Pending"
    else:
        walk_line = "Physical activity: Pending"
        
    message = f"Mecris System Alert: This is your daily activity update.\n{walk_line}.\nClozemaster Arabic: Due today.\nCurrent local temperature: 65F.\nPlease log your activity to maintain your account standing."
    
    logger.info(f"Sending reminder: {message}")
    result = smart_send_message(message, target_phone)
    
    if result.get("sent"):
        method = result.get("method", "unknown")
        logger.info(f"Message sent successfully via {method}.")
        # Log the message to enforce daily limits in the consent manager
        consent_manager.log_message_sent(
            phone_number=target_phone,
            message=message,
            message_type="walk_reminder",
            delivery_method=method
        )
    else:
        logger.error("Failed to send message.")

if __name__ == "__main__":
    run_base_reminder()
