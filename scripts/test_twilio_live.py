import os
import logging
import sys
from dotenv import load_dotenv
from twilio_sender import send_sms

# Configure logging to stderr for test output
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("twilio_test")

def test_twilio_live():
    load_dotenv()
    
    # Check for required variables
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    to_number = os.getenv("TWILIO_TO_NUMBER")
    
    print("--- Twilio Live Micro-Test ---")
    print(f"Account SID: {account_sid[:5] if account_sid else 'None'}...{account_sid[-5:] if account_sid else 'None'}")
    print(f"From: {from_number}")
    print(f"To:   {to_number}")
    
    if not all([account_sid, auth_token, from_number, to_number]):
        print("\n❌ Error: Missing Twilio credentials in .env")
        print("Required: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_TO_NUMBER")
        return

    test_msg = "🐕 Mecris Test: Live micro-test of your Twilio integration. Success!"
    
    print("\nAttempting to send message...")
    try:
        # Use existing send_sms from twilio_sender.py
        sid = send_sms(test_msg)
        print(f"✅ Success! Message SID: {sid}")
    except Exception as e:
        print(f"❌ Failed to send message: {e}")

if __name__ == "__main__":
    test_twilio_live()
