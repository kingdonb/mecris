import os
import logging
import sys
from dotenv import load_dotenv
from twilio_sender import send_message

# Configure logging to stderr for test output
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("whatsapp_test")

def test_whatsapp_live():
    load_dotenv()
    
    # Check for required variables
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    to_number = os.getenv("TWILIO_TO_NUMBER")
    
    print("--- Twilio WhatsApp Live Micro-Test ---")
    print(f"Account SID: {account_sid[:5] if account_sid else 'None'}...{account_sid[-5:] if account_sid else 'None'}")
    print(f"From: {from_number}")
    print(f"To:   {to_number}")
    
    if not all([account_sid, auth_token, from_number, to_number]):
        print("\n❌ Error: Missing Twilio/WhatsApp credentials in .env")
        print("Required: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_TO_NUMBER")
        print("Optional: TWILIO_WHATSAPP_FROM (defaults to sandbox)")
        return

    test_msg = "🧠 Mecris WhatsApp Test: This is a live micro-test of your WhatsApp integration. Success! 🚀"
    
    print("\nAttempting to send WhatsApp message...")
    try:
        # Use existing send_message (which handles WhatsApp) from twilio_sender.py
        # Note: twilio_sender.py's send_message is actually the WhatsApp sender!
        success = send_message(test_msg)
        if success:
            print(f"✅ Success! WhatsApp message SID should be in logs.")
        else:
            print(f"❌ Failed to send WhatsApp message. Check logs for details.")
    except Exception as e:
        print(f"❌ Exception while sending message: {e}")

if __name__ == "__main__":
    test_whatsapp_live()
