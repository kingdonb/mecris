import os
import json
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

client = Client(account_sid, auth_token)

print(f"Fetching WhatsApp templates for account: {account_sid[:5]}...")

try:
    # Try fetching messaging templates which is different from Content API
    templates = client.messaging.v1.domain_certs.list()
    print("This API isn't exactly right for templates, let's try HTTP direct request")
except Exception as e:
    pass

import requests
from requests.auth import HTTPBasicAuth

# Twilio API for WhatsApp templates is under the messaging/v1/services/{MessagingServiceSid}/us_app_to_person/usecases 
# Wait, let's just query the raw API for any templates

url = f"https://messaging.twilio.com/v1/Services"
response = requests.get(url, auth=HTTPBasicAuth(account_sid, auth_token))

print("Services:")
if response.status_code == 200:
    data = response.json()
    for service in data.get('services', []):
        print(f" - {service['friendly_name']} ({service['sid']})")
else:
    print(f"Error fetching services: {response.status_code}")

