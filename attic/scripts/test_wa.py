import asyncio
from twilio_sender import smart_send_message
from dotenv import load_dotenv
load_dotenv()
res = smart_send_message("Mecris diagnostics: WhatsApp messaging is functional.")
print(res)
