import os
import json
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
to_number = "whatsapp:+15852378622"
from_number = "whatsapp:+15744757115"
content_sid = "HXbb3327078f3e3361dad21f0a2dc6a8dd"

client = Client(account_sid, auth_token)

print(f"Testing Content SID: {content_sid}")
try:
    message = client.messages.create(
        from_=from_number,
        to=to_number,
        content_sid=content_sid,
        content_variables=json.dumps({
            "1": "Boris and Fiona's walk",
            "2": "Clozemaster Arabic",
            "3": "65",
            "4": "Pending",
            "5": "Due today"
        })
    )
    print(f"Message SID: {message.sid}")
except Exception as e:
    print(f"Failed: {e}")
