import os
from dotenv import load_dotenv

load_dotenv()
vars_to_check = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_WHATSAPP_FROM', 'TWILIO_TO_NUMBER', 'TWILIO_WHATSAPP_TEMPLATE_SID', 'NEON_DB_URL']
for v in vars_to_check:
    val = os.getenv(v)
    print(f"{v}: {'Set' if val else 'MISSING'}")
