import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

url = f"https://content.twilio.com/v1/Content"
payload = {
    "friendly_name": "mecris_daily_alert_v1",
    "language": "en",
    "variables": {
        "1": "activity1",
        "2": "status1",
        "3": "activity2",
        "4": "status2",
        "5": "temp"
    },
    "types": {
        "twilio/text": {
            "body": "Mecris System Alert: This is your daily activity update.\n{{1}}: {{2}}.\n{{3}}: {{4}}.\nCurrent local temperature: {{5}}F.\nPlease log your activity to maintain your account standing."
        }
    }
}

response = requests.post(url, json=payload, auth=HTTPBasicAuth(account_sid, auth_token))
print(response.status_code)
print(response.json())
