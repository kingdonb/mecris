import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
content_sid = os.getenv('TWILIO_WHATSAPP_TEMPLATE_SID')

url = f"https://content.twilio.com/v1/Content/{content_sid}/ApprovalRequests/whatsapp"
payload = {
    "name": "mecris_daily_alert_v1",
    "category": "UTILITY"
}

print(f"Submitting {content_sid} for WhatsApp approval...")
response = requests.post(url, json=payload, auth=HTTPBasicAuth(account_sid, auth_token))
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
