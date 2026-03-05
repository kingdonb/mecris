import os
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

# FIXING REJECTED TEMPLATES
# Problem: Variables at the end of the template.
# Solution: Ensure static text follows the last variable.

templates = [
    {
        "name": "mecris_status_v2",
        "body": "Mecris Status Update: Your goal {{1}} is currently {{2}}. Your commitment {{3}} is {{4}}. Please review the {{5}} update for details."
    },
    {
        "name": "mecris_activity_check_v2",
        "body": "Mecris Activity Check: Record for {{1}} is {{2}}. Status for {{3}} is {{4}}. This update was recorded at {{5}} today."
    },
    {
        "name": "mecris_budget_statement_v2",
        "body": "Mecris Budget Statement: Your current credit balance is ${{1}}, projected to last {{2}} days. Current status: {{3}} for your account."
    },
    {
        "name": "mecris_daily_briefing_v2",
        "body": "Mecris Daily Briefing: Your account has {{1}} active goals and {{2}} items requiring attention. Current status: {{3}} briefing update."
    },
    {
        "name": "mecris_system_maintenance_v2",
        "body": "Mecris System Maintenance: Account in read-only mode for {{1}} minutes starting at {{2}}. Reason: {{3}} scheduled maintenance."
    },
    {
        "name": "mecris_sync_confirmation_v2",
        "body": "Mecris Sync Confirmation: Local data from {{1}} has synchronized. Total of {{2}} updates were processed at {{3}} today."
    }
]

create_url = "https://content.twilio.com/v1/Content"
results = []

for t in templates:
    try:
        print(f"Creating Template: {t['name']}...")
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
        
        response = requests.post(create_url, json=payload, auth=HTTPBasicAuth(account_sid, auth_token))
        
        if response.status_code == 201 or response.status_code == 200:
            content = response.json()
            sid = content.get("sid")
            print(f"✅ Created {t['name']}: {sid}")
            
            # IMMEDIATELY SUBMIT FOR APPROVAL
            submit_url = f"https://content.twilio.com/v1/Content/{sid}/ApprovalRequests/whatsapp"
            submit_payload = {"name": t['name'], "category": "UTILITY"}
            
            submit_resp = requests.post(submit_url, json=submit_payload, auth=HTTPBasicAuth(account_sid, auth_token))
            if submit_resp.status_code in [200, 201]:
                print(f"  🚀 Submitted {t['name']} for approval.")
                results.append({"name": t['name'], "sid": sid, "status": "submitted"})
            else:
                print(f"  ❌ Failed to submit {t['name']}: {submit_resp.status_code}")
                results.append({"name": t['name'], "sid": sid, "status": "created_only"})
        else:
            print(f"❌ Failed to create {t['name']}: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error fixing {t['name']}: {e}")

# Save results
with open("data/fixed_templates.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nFix process complete. Results saved to data/fixed_templates.json")
