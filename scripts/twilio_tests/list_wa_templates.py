import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
# We can't query standard templates easily via basic API, but if you created it in the WhatsApp Sandbox or WhatsApp Senders, 
# you might just need to send the EXACT text.
print("We need the exact text to trigger the legacy WhatsApp template.")
