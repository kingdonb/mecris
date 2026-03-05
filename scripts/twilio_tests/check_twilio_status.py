import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
client = Client(account_sid, auth_token)

print("Fetching last 5 WhatsApp messages...")
messages = client.messages.list(limit=5)

for record in messages:
    print(f"---")
    print(f"SID: {record.sid}")
    print(f"Status: {record.status}")
    print(f"To: {record.to}")
    print(f"Error Code: {record.error_code}")
    print(f"Error Message: {record.error_message}")
    print(f"Body (if available): {record.body}")
    print(f"Date Sent: {record.date_sent}")
