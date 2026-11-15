import os
import json
import logging
from dotenv import load_dotenv
from twilio_sender import smart_send_message, send_whatsapp_template

logging.basicConfig(level=logging.INFO)
load_dotenv()

# Test sending a mock walk reminder
print("Testing smart_send_message...")
test_msg = "🐕 Afternoon walk time! Boris and Fiona are ready for their adventure."
result = smart_send_message(test_msg)
print(f"Result: {json.dumps(result, indent=2)}")
