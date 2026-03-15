import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

def debug_template(sid):
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    client = Client(account_sid, auth_token)
    
    try:
        content = client.content.v1.contents(sid).fetch()
        print(f"Template: {sid}")
        print(f"Friendly Name: {content.friendly_name}")
        print(f"Types: {content.types}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # activity_check_v2
    debug_template("HX9e6692d8a5689ee3c0b855f43092563a")
    # urgency_alert_v2
    debug_template("HX638b7f9403e04c8fa880370f1b7a9ba1")
