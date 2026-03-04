import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
data = {
    "To": "whatsapp:+15852378622",
    "From": "whatsapp:+15744757115",
    "Body": "Mecris System Alert: This is your daily activity update.\nBoris and Fiona's walk: Pending.\nClozemaster Arabic: Due today.\nCurrent local temperature: 65F.\nPlease log your activity to maintain your account standing."
}

# The Twilio API sometimes expects exactly matched strings to trigger standard templates without content SIDs.
# Let's ensure the exact string is being sent.
response = requests.post(url, data=data, auth=HTTPBasicAuth(account_sid, auth_token))
print(f"Status: {response.status_code}")
print(response.json().get('sid'))
