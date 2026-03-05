import os
import requests
import json
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

# Read pending templates from data file
try:
    with open("data/clever_templates.json", "r") as f:
        pending_templates = json.load(f)
except FileNotFoundError:
    print("Error: clever_templates.json not found. Run create_clever_utility_templates.py first.")
    exit(1)

for template in pending_templates:
    content_sid = template['sid']
    name = template['name']
    
    url = f"https://content.twilio.com/v1/Content/{content_sid}/ApprovalRequests/whatsapp"
    payload = {
        "name": name,
        "category": "UTILITY"
    }

    print(f"Submitting {name} ({content_sid}) for WhatsApp approval...")
    try:
        response = requests.post(url, json=payload, auth=HTTPBasicAuth(account_sid, auth_token))
        if response.status_code == 201 or response.status_code == 200:
             print(f"✅ Submitted {name} successfully!")
        else:
             print(f"❌ Failed to submit {name}: {response.status_code}")
             print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error submitting {name}: {e}")

print("\nBulk submission complete.")
