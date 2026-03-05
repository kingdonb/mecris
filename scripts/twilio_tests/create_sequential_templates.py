import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

templates = [
    {
        "name": "mecris_activity_report_v1",
        "body": "Mecris Activity Report: {{1}} is currently {{2}}. {{3}} is currently {{4}}. Status updated at {{5}}."
    },
    {
        "name": "mecris_simple_alert_v1",
        "body": "Mecris Alert: {{1}} status is {{2}}. {{3}} status is {{4}}. System status: {{5}}."
    }
]

url = "https://content.twilio.com/v1/Content"

for t in templates:
    print(f"Creating {t['name']}...")
    payload = {
        "friendly_name": t['name'],
        "language": "en",
        "variables": {str(i+1): "placeholder" for i in range(5)},
        "types": {
            "twilio/text": {
                "body": t['body']
            }
        }
    }
    
    resp = requests.post(url, json=payload, auth=HTTPBasicAuth(account_sid, auth_token))
    if resp.status_code in [200, 201]:
        sid = resp.json().get('sid')
        print(f"✅ Created: {sid}")
        submit_url = f"https://content.twilio.com/v1/Content/{sid}/ApprovalRequests/whatsapp"
        submit_resp = requests.post(submit_url, json={"name": t['name'], "category": "UTILITY"}, auth=HTTPBasicAuth(account_sid, auth_token))
        if submit_resp.status_code in [200, 201]:
            print(f"  🚀 Submitted for approval.")
    else:
        print(f"❌ Failed: {resp.text}")
