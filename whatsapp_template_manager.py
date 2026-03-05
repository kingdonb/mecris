import os
import json
import logging
from typing import List, Dict, Any
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("mecris.template_manager")

class WhatsAppTemplateManager:
    def __init__(self, account_sid: str = None, auth_token: str = None):
        self.account_sid = account_sid or os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = auth_token or os.getenv('TWILIO_AUTH_TOKEN')
        if not self.account_sid or not self.auth_token:
            raise ValueError("Twilio credentials missing")
        self.client = Client(self.account_sid, self.auth_token)
        self.data_path = "data/approved_templates.json"

    def fetch_all_statuses(self) -> List[Dict[str, Any]]:
        """Fetch all templates and their approval statuses from Twilio."""
        try:
            templates = self.client.content.v1.content_and_approvals.stream()
            results = []
            for record in templates:
                # record.approval_requests is often a list or dict
                approval = record.approval_requests
                if isinstance(approval, list) and len(approval) > 0:
                    approval = approval[0] # Usually the first one is WhatsApp
                
                if not approval:
                    approval = {}
                    
                status = approval.get('status', 'unknown') if isinstance(approval, dict) else getattr(approval, 'status', 'unknown')
                category = approval.get('category', 'unknown') if isinstance(approval, dict) else getattr(approval, 'category', 'unknown')
                
                results.append({
                    "sid": record.sid,
                    "name": record.friendly_name,
                    "status": status,
                    "category": category
                })
            return results
        except Exception as e:
            logger.error(f"Failed to fetch template statuses: {e}")
            return []

    def get_approved_pool(self) -> List[str]:
        """Get only approved template SIDs."""
        all_templates = self.fetch_all_statuses()
        return [t['sid'] for t in all_templates if t['status'] == 'approved']

    def sync_approved_templates(self) -> int:
        """Sync approved templates to local storage."""
        all_templates = self.fetch_all_statuses()
        approved = {t['sid']: t['name'] for t in all_templates if t['status'] == 'approved'}
        with open(self.data_path, 'w') as f:
            json.dump({
                "approved_templates": approved,
                "last_updated": os.getenv('CURRENT_DATE', 'unknown')
            }, f, indent=2)
        return len(approved)

if __name__ == "__main__":
    manager = WhatsAppTemplateManager()
    count = manager.sync_approved_templates()
    print(f"Synced {count} approved templates.")
