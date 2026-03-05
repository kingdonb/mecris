import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from twilio_sender import smart_send_message

class TestIssue52TemplateMapping(unittest.TestCase):
    def setUp(self):
        os.environ['TWILIO_WHATSAPP_TEMPLATE_SID'] = 'HXbb3327078f3e3361dad21f0a2dc6a8dd'
        os.environ['REMINDER_DELIVERY_METHOD'] = 'whatsapp'
        os.environ['TWILIO_ACCOUNT_SID'] = 'ACtest'
        os.environ['TWILIO_AUTH_TOKEN'] = 'test'
        os.environ['TWILIO_WHATSAPP_FROM'] = 'whatsapp:+14155238886'
        os.environ['TWILIO_TO_NUMBER'] = '+15555555555'

    @patch('twilio_sender.send_whatsapp_template')
    @patch('sms_consent_manager.consent_manager.get_user_preferences')
    def test_smart_send_message_mapping_normal(self, mock_get_prefs, mock_send_template):
        # Normal mode: vacation_mode = False
        mock_get_prefs.return_value = {"preferences": {"vacation_mode": False}}
        mock_send_template.return_value = True
        
        message = "Mecris System Alert: ... Physical activity: Pending ..."
        smart_send_message(message)
        
        # Verify the variables sent to Twilio
        args, kwargs = mock_send_template.call_args
        variables = args[1]
        
        # mecris_daily_alert_v1 template structure:
        # {{1}}: {{2}}
        # {{3}}: {{4}}
        # Current local temperature: {{5}}F
        
        self.assertEqual(variables["1"], "Boris & Fiona walk")
        self.assertEqual(variables["2"], "Pending")
        self.assertEqual(variables["3"], "Clozemaster Arabic")
        self.assertEqual(variables["4"], "Due today")
        self.assertEqual(variables["5"], "65") # Mocked message has 65F

    @patch('twilio_sender.send_whatsapp_template')
    @patch('sms_consent_manager.consent_manager.get_user_preferences')
    def test_smart_send_message_mapping_vacation(self, mock_get_prefs, mock_send_template):
        # Vacation mode: vacation_mode = True
        mock_get_prefs.return_value = {"preferences": {"vacation_mode": True}}
        mock_send_template.return_value = True
        
        message = "Mecris System Alert: ... Activity log: Pending ... Daily commitment: Review needed ... 65F"
        smart_send_message(message)
        
        # Verify the variables sent to Twilio
        args, kwargs = mock_send_template.call_args
        variables = args[1]
        
        self.assertEqual(variables["1"], "Activity log")
        self.assertEqual(variables["2"], "Pending")
        self.assertEqual(variables["3"], "Daily commitment")
        self.assertEqual(variables["4"], "Review needed")
        self.assertEqual(variables["5"], "65")

if __name__ == '__main__':
    unittest.main()
