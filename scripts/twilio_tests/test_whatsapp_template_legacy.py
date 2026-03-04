import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
to_number = "whatsapp:+15852378622"
from_number = "whatsapp:+15744757115"

client = Client(account_sid, auth_token)

# In the older WhatsApp template system, you just send the exact text of the template,
# or you use the Content API. If Content API says "create your first", then it's a legacy WhatsApp template.
# Let's try sending exactly what a template might look like if it was approved yesterday.
# I will fetch the message logs to see what error came back for SMea74618e01d2bde090994f0b274303f1

message = client.messages('SMea74618e01d2bde090994f0b274303f1').fetch()
print(f"Status of recent test: {message.status}")
if message.error_code:
    print(f"Error Code: {message.error_code}")
    print(f"Error Message: {message.error_message}")

