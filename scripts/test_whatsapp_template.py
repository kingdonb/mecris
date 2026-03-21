import os
import json
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

def test_template():
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_WHATSAPP_FROM')
    to_number = os.getenv('TWILIO_TO_NUMBER')
    
    # mecris_status_v2 (Known working yesterday)
    content_sid = "HX9403f1b85350b8c05780a1128b79f3c2"
    variables = {
        "1": "Daily Walk",
        "2": "NOT FOUND",
        "3": "Boris & Fiona",
        "4": "EXPECTANT",
        "5": "01:53 PM"
    }
    
    if not to_number.startswith('whatsapp:'):
        to_number = f'whatsapp:{to_number}'

    client = Client(account_sid, auth_token)
    try:
        message = client.messages.create(
            from_=from_number,
            to=to_number,
            content_sid=content_sid,
            content_variables=json.dumps(variables)
        )
        print(f"Sent test template {content_sid}. SID: {message.sid}")
    except Exception as e:
        print(f"Failed to send test template: {e}")

if __name__ == "__main__":
    test_template()
