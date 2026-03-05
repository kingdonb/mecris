import os
import json
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
to_number = f"whatsapp:{os.getenv('TWILIO_TO_NUMBER', '').replace('whatsapp:', '')}"
from_number = os.getenv('TWILIO_WHATSAPP_FROM')
content_sid = os.getenv('TWILIO_WHATSAPP_TEMPLATE_SID')

client = Client(account_sid, auth_token)

print(f"Testing Content SID: {content_sid}")
try:
    message = client.messages.create(
        from_=from_number,
        to=to_number,
        content_sid=content_sid,
        content_variables=json.dumps({
            "1": "Boris and Fiona's walk",
            "2": "Pending",
            "3": "Clozemaster Arabic",
            "4": "Due today",
            "5": "65"
        })
    )
    print(f"Message SID: {message.sid}")
except Exception as e:
    print(f"Failed: {e}")
