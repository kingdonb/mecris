import os
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

# 10 CLEVER UTILITY TEMPLATES (ACCOUNT ALERTS / SERVICE UPDATES)
# Guidelines:
# - No marketing/promotional language.
# - High text-to-variable ratio (to avoid rejection).
# - Strictly transactional/informational about the user's account.

templates = [
    {
        "name": "mecris_daily_briefing_v1",
        "body": "Mecris Daily Briefing: Your account currently has {{1}} active goals. {{2}} items require attention before the next sync. Current status: {{3}}."
    },
    {
        "name": "mecris_urgency_alert_v2",
        "body": "Mecris Urgency Alert: Your goal '{{1}}' has reached a critical threshold and will expire in {{2}}. Action is required to maintain your account standing."
    },
    {
        "name": "mecris_activity_verification_v1",
        "body": "Mecris Activity Verification: No data was detected for '{{1}}' today. If you have completed this, please log it now to update your {{2}} status."
    },
    {
        "name": "mecris_budget_statement_v1",
        "body": "Mecris Budget Statement: Your current credit balance is ${{1}}, which is projected to last {{2}} days at your current burn rate. Status: {{3}}."
    },
    {
        "name": "mecris_sync_confirmation_v1",
        "body": "Mecris Sync Confirmation: Your local data from {{1}} has been successfully synchronized with the cloud. {{2}} updates were processed at {{3}}."
    },
    {
        "name": "mecris_vacation_status_v1",
        "body": "Mecris Account Update: Vacation Mode is currently {{1}}. Your regular reminders for {{2}} are suppressed until {{3}}. Personal goals remain active."
    },
    {
        "name": "mecris_milestone_notice_v1",
        "body": "Mecris Milestone Notice: Your account has reached a new threshold of {{1}} for the goal '{{2}}'. This has been recorded in your permanent history."
    },
    {
        "name": "mecris_preference_update_v1",
        "body": "Mecris Preference Update: Your messaging window has been updated to {{1}} to {{2}}. You will receive no further automated alerts outside this window."
    },
    {
        "name": "mecris_security_checkpoint_v1",
        "body": "Mecris Security Checkpoint: A new login was detected for your account from {{1}}. If this was not you, please update your {{2}} settings immediately."
    },
    {
        "name": "mecris_system_maintenance_v1",
        "body": "Mecris System Maintenance: Your account will be in read-only mode for {{1}} minutes starting at {{2}} for scheduled updates. Status: {{3}}."
    }
]

url = "https://content.twilio.com/v1/Content"
results = []

for t in templates:
    try:
        print(f"Creating Template: {t['name']}...")
        # Create a dummy variables dict for the 'variables' field (required by some SDKs/parsers)
        # But for the raw API, we just need the body with placeholders.
        payload = {
            "friendly_name": t['name'],
            "language": "en",
            "variables": {str(i+1): "placeholder" for i in range(5)},
            "types": {
                "twilio/text": {
                    "body": t['body']
                }
            }
        }
        
        response = requests.post(url, json=payload, auth=HTTPBasicAuth(account_sid, auth_token))
        
        if response.status_code == 201 or response.status_code == 200:
            content = response.json()
            sid = content.get("sid")
            print(f"✅ Created {t['name']}: {sid}")
            results.append({"name": t['name'], "sid": sid})
        else:
            print(f"❌ Failed {t['name']}: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error {t['name']}: {e}")

# Save for submission
with open("data/clever_templates.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nSubmission summary saved to data/clever_templates.json")
