#!/usr/bin/env python3
"""
Test script for Mecris Intelligent Reminder System
Tests all three tiers and delivery modes
"""

import requests
import json
from datetime import datetime

def test_reminder_check():
    """Test the reminder check endpoint"""
    print("🔍 Testing reminder check endpoint...")
    try:
        response = requests.get("http://localhost:8000/intelligent-reminder/check")
        result = response.json()
        print(f"✅ Reminder check: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        print(f"❌ Reminder check failed: {e}")
        return None

def test_message_send(message, message_type="test"):
    """Test message sending (will fail without Twilio creds, but shows the flow)"""
    print(f"📤 Testing message send: {message}")
    try:
        response = requests.post(
            "http://localhost:8000/intelligent-reminder/send",
            json={
                "message": message,
                "type": message_type,
                "tier": "base_mode"
            }
        )
        result = response.json()
        print(f"📱 Send result: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        print(f"❌ Message send failed: {e}")
        return None

def test_full_trigger():
    """Test the complete trigger workflow"""
    print("🚀 Testing full trigger workflow...")
    try:
        response = requests.post("http://localhost:8000/intelligent-reminder/trigger")
        result = response.json()
        print(f"🎯 Trigger result: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        print(f"❌ Full trigger failed: {e}")
        return None

def test_narrator_context():
    """Test that we can get context without consuming Claude credits"""
    print("📊 Testing narrator context access...")
    try:
        response = requests.get("http://localhost:8000/narrator/context")
        result = response.json()
        
        # Extract key info
        walk_status = result.get("daily_walk_status", {})
        budget_status = result.get("budget_status", {})
        
        print(f"🚶‍♂️ Walk status: {walk_status.get('status', 'unknown')}")
        print(f"💰 Budget remaining: ${budget_status.get('remaining_budget', 0):.2f}")
        print(f"📈 Budget tier: {'base_mode' if budget_status.get('remaining_budget', 0) < 0.5 else 'smart_template' if budget_status.get('remaining_budget', 0) < 2.0 else 'enhanced'}")
        
        return result
    except Exception as e:
        print(f"❌ Context check failed: {e}")
        return None

if __name__ == "__main__":
    print("🧠 Mecris Intelligent Reminder System Test")
    print("=" * 50)
    
    # Test context access (no Claude credits used)
    context = test_narrator_context()
    print()
    
    # Test reminder logic
    check_result = test_reminder_check()
    print()
    
    # Test message delivery (will show error without Twilio, but that's expected)
    send_result = test_message_send("🧪 Test message from reminder system", "test")
    print()
    
    # Test full workflow
    trigger_result = test_full_trigger()
    print()
    
    print("📋 Test Summary:")
    print(f"Context Access: {'✅' if context else '❌'}")
    print(f"Reminder Check: {'✅' if check_result else '❌'}")
    print(f"Message Send: {'🔧' if send_result and 'error' in send_result else '✅' if send_result else '❌'} (Twilio config needed)")
    print(f"Full Trigger: {'✅' if trigger_result else '❌'}")
    
    if context and check_result:
        print("\n🎉 Core system is working!")
        print("Next steps:")
        print("1. Configure Twilio credentials in .env")
        print("2. Run ./setup_reminder_cron.sh to install cron job")
        print("3. Walk reminders will work even with $0 Claude budget")
    else:
        print("\n⚠️ Some tests failed - check MCP server is running")