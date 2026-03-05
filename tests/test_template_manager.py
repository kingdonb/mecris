import unittest
from unittest.mock import patch, MagicMock
import os
import json
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whatsapp_template_manager import WhatsAppTemplateManager

class TestWhatsAppTemplateManager(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('whatsapp_template_manager.Client')
        self.mock_client_class = self.patcher.start()
        self.mock_client = self.mock_client_class.return_value
        self.manager = WhatsAppTemplateManager(account_sid="ACtest", auth_token="test")
        self.manager.data_path = "tests/test_approved_templates.json"

    def tearDown(self):
        self.patcher.stop()

    def test_fetch_all_statuses(self):
        # Mock the Twilio stream
        mock_record1 = MagicMock()
        mock_record1.sid = "HX1"
        mock_record1.friendly_name = "Template 1"
        mock_record1.approval_requests = {"status": "approved", "category": "UTILITY"}
        
        mock_record2 = MagicMock()
        mock_record2.sid = "HX2"
        mock_record2.friendly_name = "Template 2"
        mock_record2.approval_requests = {"status": "rejected", "category": "MARKETING"}
        
        # Configure the nested mock
        self.mock_client.content.v1.content_and_approvals.stream.return_value = [mock_record1, mock_record2]
        
        statuses = self.manager.fetch_all_statuses()
        
        self.assertEqual(len(statuses), 2)
        self.assertEqual(statuses[0]['status'], "approved")
        self.assertEqual(statuses[1]['status'], "rejected")

    @patch('whatsapp_template_manager.WhatsAppTemplateManager.fetch_all_statuses')
    def test_get_approved_pool(self, mock_fetch):
        mock_fetch.return_value = [
            {"sid": "HX1", "status": "approved"},
            {"sid": "HX2", "status": "rejected"},
            {"sid": "HX3", "status": "approved"}
        ]
        
        pool = self.manager.get_approved_pool()
        self.assertEqual(pool, ["HX1", "HX3"])

    @patch('whatsapp_template_manager.WhatsAppTemplateManager.get_approved_pool')
    def test_sync_approved_templates(self, mock_get_pool):
        mock_get_pool.return_value = ["HX1", "HX3"]
        
        if os.path.exists(self.manager.data_path):
            os.remove(self.manager.data_path)
            
        count = self.manager.sync_approved_templates()
        
        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(self.manager.data_path))
        
        with open(self.manager.data_path, 'r') as f:
            data = json.load(f)
            self.assertEqual(data['approved_sids'], ["HX1", "HX3"])
            
        os.remove(self.manager.data_path)

if __name__ == '__main__':
    unittest.main()
