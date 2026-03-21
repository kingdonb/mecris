import os
import json
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

def list_content_templates():
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    
    # The Content API is slightly different in the SDK
    # It's under client.content.v1.contents
    client = Client(account_sid, auth_token)
    
    print("Live Content Templates on Twilio:")
    print("-" * 40)
    
    templates = client.content.v1.contents.list(limit=50)
    live_list = {}
    for record in templates:
        print(f"Name: {record.friendly_name}")
        print(f"SID: {record.sid}")
        # To get status, we often have to fetch the individual record or check types
        # But for now, just listing what EXISTS is enough based on user's instruction
        live_list[record.sid] = record.friendly_name
        print("-" * 20)
    
    return live_list

if __name__ == "__main__":
    live_list = list_content_templates()
    
    # Load local list
    with open('data/approved_templates.json', 'r') as f:
        local_data = json.load(f)
    local_list = local_data.get('approved_templates', {})
    
    print("\nComparison Analysis:")
    print("-" * 40)
    
    deleted = []
    for sid, name in local_list.items():
        if sid not in live_list:
            deleted.append((sid, name))
            
    if not deleted:
        print("✅ No mismatches! All local templates exist on Twilio.")
    else:
        print(f"❌ Found {len(deleted)} templates in local data that were DELETED from Twilio:")
        for sid, name in deleted:
            print(f"  - {name} ({sid})")
            
    surprises = []
    for sid, name in live_list.items():
        if sid not in local_list:
            surprises.append((sid, name))
            
    if surprises:
        print(f"\n✨ Found {len(surprises)} templates on Twilio NOT in local data:")
        for sid, name in surprises:
            print(f"  - {name} ({sid})")
