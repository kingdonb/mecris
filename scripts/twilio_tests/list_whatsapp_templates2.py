import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import json

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

print("Fetching WhatsApp templates via Meta/WhatsApp API endpoint...")
# The endpoint for WhatsApp templates is different.
# Since we know the template name is 'mecris_status_update', let's just try to send it and see if it fails with a specific error that gives us a hint, or if we need to configure Content SID differently.

url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
data = {
    "To": f"whatsapp:{os.getenv('TWILIO_TO_NUMBER', '').replace('whatsapp:', '')}",
    "From": os.getenv('TWILIO_WHATSAPP_FROM'),
    "Body": "Trying to use template: mecris_status_update"
}

response = requests.post(url, data=data, auth=HTTPBasicAuth(account_sid, auth_token))
print(f"Status: {response.status_code}")
print(json.dumps(response.json(), indent=2))
