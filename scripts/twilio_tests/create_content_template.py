import os
import json
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

client = Client(account_sid, auth_token)

try:
    print("Creating Content Template...")
    content = client.content.v1.contents.create(
        friendly_name='mecris_daily_alert_v1',
        variables={
            "1": "Boris and Fiona's walk",
            "2": "Pending",
            "3": "Clozemaster Arabic",
            "4": "Due today",
            "5": "65"
        },
        types={
            "twilio/text": {
                "body": "Mecris System Alert: This is your daily activity update.\n{{1}}: {{2}}.\n{{3}}: {{4}}.\nCurrent local temperature: {{5}}F.\nPlease log your activity to maintain your account standing."
            }
        }
    )
    
    print(f"✅ Created Content Template successfully!")
    print(f"Content SID: {content.sid}")
    
    # We must also submit it for WhatsApp approval. 
    # To do this we need to know your WhatsApp Sender ID or we can just create it first.
except Exception as e:
    print(f"Error creating template: {e}")
