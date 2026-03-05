import os
import json
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

client = Client(account_sid, auth_token)

# PROPOSED TEMPLATE CONTENT:
# Body: Mecris Account Update: Your status for {{1}} is {{2}}. Status for {{3}} is {{4}}. Please review your progress and complete your daily log.
# Variables mapping (Normal):
# 1: Physical Activity
# 2: Pending
# 3: Daily commitment
# 4: Due today
#
# Variables mapping (Vacation Mode):
# 1: Activity log
# 2: Pending
# 3: Daily commitment
# 4: Up to date

try:
    print("Creating Utility Template v2...")
    content = client.content.v1.contents.create(
        friendly_name='mecris_daily_alert_v2',
        variables={
            "1": "Physical Activity",
            "2": "Pending",
            "3": "Daily commitment",
            "4": "Due today"
        },
        types={
            "twilio/text": {
                "body": "Mecris Account Update: Your status for {{1}} is {{2}}. Status for {{3}} is {{4}}. Please review your progress and complete your daily log."
            }
        }
    )
    
    print(f"✅ Created Content Template successfully!")
    print(f"Content SID: {content.sid}")
    print(f"Next step: Set TWILIO_WHATSAPP_TEMPLATE_SID={content.sid} in .env and run approval script.")
    
except Exception as e:
    print(f"Error creating template: {e}")
