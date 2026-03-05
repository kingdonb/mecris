import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
to_number = f"whatsapp:{os.getenv('TWILIO_TO_NUMBER', '').replace('whatsapp:', '')}"
from_number = os.getenv('TWILIO_WHATSAPP_FROM')

client = Client(account_sid, auth_token)

# In the older WhatsApp template system, you just send the exact text of the template,
# or you use the Content API. If Content API says "create your first", then it's a legacy WhatsApp template.
# Let's try sending exactly what a template might look like if it was approved yesterday.
# I will fetch the message logs to see what error came back for SMea74618e01d2bde090994f0b274303f1

message = client.messages(os.getenv('TWILIO_TEST_MESSAGE_SID', 'SM_REPLACE_ME')).fetch()
print(f"Status of recent test: {message.status}")
if message.error_code:
    print(f"Error Code: {message.error_code}")
    print(f"Error Message: {message.error_message}")

