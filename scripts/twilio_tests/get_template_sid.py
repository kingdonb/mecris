import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

print(f"Account SID: {account_sid[:5]}...")

client = Client(account_sid, auth_token)

try:
    print("Fetching contents...")
    contents = client.content.v1.contents.list(limit=50)
    for content in contents:
        print(f"Name: {content.friendly_name}, SID: {content.sid}")
except Exception as e:
    print(f"Error fetching contents: {e}")
