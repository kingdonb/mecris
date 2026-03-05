import os
import json
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

client = Client(account_sid, auth_token)

# BULK TEMPLATE PLANNING (UTILITY CATEGORY)
# These follow strict transactional patterns for "Account Alerts"

templates = [
    {
        "friendly_name": "mecris_status_v1",
        "body": "Mecris Status Update: Your {{1}} is {{2}}. Your {{3}} is {{4}}. Review: {{5}}"
    },
    {
        "friendly_name": "mecris_goal_reminder_v1",
        "body": "Mecris Reminder: Your {{1}} goal status is {{2}}. Status for {{3}} is {{4}}. Update your log."
    },
    {
        "friendly_name": "mecris_activity_check_v1",
        "body": "Mecris Activity Check: {{1}} currently {{2}}. {{3}} currently {{4}}. Status timestamp: {{5}}"
    }
]

created_templates = []

for t in templates:
    try:
        print(f"Creating Template: {t['friendly_name']}...")
        content = client.content.v1.contents.create(
            friendly_name=t['friendly_name'],
            language='en',
            types={
                "twilio/text": {
                    "body": t['body']
                }
            }
        )
        print(f"✅ Created {t['friendly_name']}: {content.sid}")
        created_templates.append({"name": t['friendly_name'], "sid": content.sid})
    except Exception as e:
        print(f"Error creating {t['friendly_name']}: {e}")

# Save results for submission script
with open("data/pending_templates.json", "w") as f:
    json.dump(created_templates, f, indent=2)

print("\n--- Summary ---")
for ct in created_templates:
    print(f"{ct['name']}: {ct['sid']}")
print("\nNext: Run scripts/twilio_tests/submit_bulk_approval.py")
