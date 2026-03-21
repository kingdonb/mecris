import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

def check_messages():
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    client = Client(account_sid, auth_token)
    
    print("Recent messages:")
    messages = client.messages.list(limit=15)
    for record in messages:
        print(f"SID: {record.sid}")
        print(f"  Date: {record.date_created}")
        print(f"  To: {record.to}")
        print(f"  Status: {record.status}")
        print(f"  Body: {record.body[:100]}...")
        if record.error_code:
            print(f"  Error Code: {record.error_code}")
        print("-" * 20)

if __name__ == "__main__":
    check_messages()
