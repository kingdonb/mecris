import os
import json
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
to_number = "whatsapp:+15852378622"
from_number = "whatsapp:+15744757115"

client = Client(account_sid, auth_token)

# Try sending via Content API again with proper variables
content_sid = 'HX5798991275215c2cf083bb7c244bcebe'  # Needs an actual SID

# Get the contents first to find the SID
contents = client.content.v1.contents.list(limit=10)
target_sid = None
for content in contents:
    if "status" in content.friendly_name.lower() or "alert" in content.friendly_name.lower() or "daily" in content.friendly_name.lower() or "mecris" in content.friendly_name.lower():
        target_sid = content.sid
        print(f"Found template: {content.friendly_name} -> {content.sid}")

if target_sid:
    print(f"Sending with Content SID: {target_sid}")
    message = client.messages.create(
        from_=from_number,
        to=to_number,
        content_sid=target_sid,
        content_variables=json.dumps({
            "1": "Boris and Fiona's walk",
            "2": "Pending",
            "3": "Clozemaster Arabic",
            "4": "Due today",
            "5": "65"
        })
    )
    print(f"Message SID: {message.sid}")
else:
    print("Could not find a Content SID for the new template. Is it a Content API template or just a WhatsApp template?")

