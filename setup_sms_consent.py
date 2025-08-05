#!/usr/bin/env python3
"""
Setup SMS consent for the primary user (A2P compliance bootstrap)
"""

import os
from sms_consent_manager import consent_manager
from dotenv import load_dotenv

load_dotenv()

def setup_primary_user():
    """Set up SMS consent for the primary system user"""
    
    phone_number = os.getenv('TWILIO_TO_NUMBER')
    if not phone_number:
        print("❌ TWILIO_TO_NUMBER not found in environment")
        print("Please set your phone number in .env file")
        return False
    
    print(f"🧠 Setting up SMS consent for {phone_number}")
    
    # Opt in the primary user for all message types
    result = consent_manager.opt_in_user(
        phone_number=phone_number,
        consent_method="system_setup",
        message_types=["walk_reminder", "budget_alert", "beeminder_emergency", "system_alert"]
    )
    
    print("✅ SMS consent configured!")
    print(f"   Phone: {phone_number}")
    print(f"   Opted in: {result['opted_in']}")
    print(f"   Message types: {', '.join(result['message_types'])}")
    print(f"   Time window: {result['preferences']['time_window_start']}-{result['preferences']['time_window_end']}")
    
    # Test consent check
    check = consent_manager.can_send_message(phone_number, "walk_reminder")
    print(f"\n🔍 Walk reminder consent check: {check['can_send']}")
    if not check['can_send']:
        print(f"   Reason: {check['reason']}")
    
    return True

if __name__ == "__main__":
    print("🚀 Mecris SMS Consent Setup")
    print("=" * 40)
    
    if setup_primary_user():
        print("\n🎉 SMS consent system ready!")
        print("\nNext steps:")
        print("1. A2P campaign approval from Twilio")
        print("2. Set REMINDER_DELIVERY_METHOD=sms in .env")
        print("3. Test with: curl -X POST http://localhost:8000/intelligent-reminder/trigger")
        print("\n📋 Compliance status: Ready for A2P messaging")
    else:
        print("\n⚠️  Setup incomplete - check configuration")