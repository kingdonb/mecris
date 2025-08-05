#!/usr/bin/env python3
"""
Mocked SMS Testing for Mecris
Tests SMS/WhatsApp functionality without sending real messages
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from twilio_sender import send_sms, send_message, smart_send_message, budget_alert


class TestSMSMocked(unittest.TestCase):
    """Test SMS functionality with mocked Twilio client"""
    
    def setUp(self):
        """Set up test environment variables"""
        self.test_env_vars = {
            'TWILIO_ACCOUNT_SID': 'test_account_sid',
            'TWILIO_AUTH_TOKEN': 'test_auth_token',
            'TWILIO_FROM_NUMBER': '+1234567890',
            'TWILIO_TO_NUMBER': '+0987654321',
            'TWILIO_WHATSAPP_FROM': 'whatsapp:+14155238886'
        }
        
        # Set environment variables for tests
        for key, value in self.test_env_vars.items():
            os.environ[key] = value
    
    def tearDown(self):
        """Clean up environment variables"""
        for key in self.test_env_vars.keys():
            os.environ.pop(key, None)
    
    @patch('twilio_sender.Client')
    def test_send_sms_success(self, mock_client_class):
        """Test successful SMS sending"""
        # Mock the Twilio client and message
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = 'test_message_sid_123'
        
        mock_client.messages.create.return_value = mock_message
        mock_client_class.return_value = mock_client
        
        # Test SMS sending
        result = send_sms("Test message")
        
        # Verify call was made correctly
        self.assertTrue(result)
        mock_client_class.assert_called_once_with('test_account_sid', 'test_auth_token')
        mock_client.messages.create.assert_called_once_with(
            body="Test message",
            from_='+1234567890',
            to='+0987654321'
        )
    
    @patch('twilio_sender.Client')
    def test_send_sms_failure(self, mock_client_class):
        """Test SMS sending failure"""
        # Mock client to raise exception
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Twilio API error")
        mock_client_class.return_value = mock_client
        
        # Test SMS sending
        result = send_sms("Test message")
        
        # Verify failure is handled correctly
        self.assertFalse(result)
    
    def test_send_sms_missing_credentials(self):
        """Test SMS sending with missing credentials"""
        # Remove required environment variable
        os.environ.pop('TWILIO_ACCOUNT_SID', None)
        
        # Test SMS sending
        result = send_sms("Test message")
        
        # Verify failure
        self.assertFalse(result)
    
    @patch('twilio_sender.Client')
    def test_send_whatsapp_success(self, mock_client_class):
        """Test successful WhatsApp message sending"""
        # Mock the Twilio client and message
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = 'test_whatsapp_sid_456'
        
        mock_client.messages.create.return_value = mock_message
        mock_client_class.return_value = mock_client
        
        # Test WhatsApp sending
        result = send_message("Test WhatsApp message")
        
        # Verify call was made correctly
        self.assertTrue(result)
        mock_client_class.assert_called_once_with('test_account_sid', 'test_auth_token')
        mock_client.messages.create.assert_called_once_with(
            body="Test WhatsApp message",
            from_='whatsapp:+14155238886',
            to='whatsapp:+0987654321'  # Should auto-prefix with whatsapp:
        )
    
    @patch('twilio_sender.Client')
    def test_send_whatsapp_custom_number(self, mock_client_class):
        """Test WhatsApp with custom to number"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = 'test_custom_sid'
        
        mock_client.messages.create.return_value = mock_message
        mock_client_class.return_value = mock_client
        
        # Test with custom number
        result = send_message("Custom message", to_number="+1555000123")
        
        self.assertTrue(result)
        mock_client.messages.create.assert_called_once_with(
            body="Custom message",
            from_='whatsapp:+14155238886',
            to='whatsapp:+1555000123'
        )
    
    @patch('twilio_sender.send_message')
    def test_budget_alert_critical(self, mock_send_message):
        """Test critical budget alert"""
        mock_send_message.return_value = True
        
        # Test critical alert (less than 2 days left)
        budget_alert(2.50, 2.00)  # 1.25 days left
        
        # Verify critical alert was sent
        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args[0][0]
        self.assertIn("🚨 CRITICAL", call_args)
        self.assertIn("$2.50 remaining", call_args)
        self.assertIn("$2.00/day burn rate", call_args)
    
    @patch('twilio_sender.send_message')
    def test_budget_alert_warning(self, mock_send_message):
        """Test warning budget alert"""
        mock_send_message.return_value = True
        
        # Test warning alert (3 days left)
        budget_alert(9.00, 3.00)  # 3 days left
        
        # Verify warning alert was sent
        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args[0][0]
        self.assertIn("⚠️ WARNING", call_args)
        self.assertIn("$9.00 remaining", call_args)
    
    @patch('twilio_sender.send_message')
    def test_budget_alert_no_spam(self, mock_send_message):
        """Test that budget alert doesn't spam when budget is fine"""
        # Test with plenty of budget (over 5 days)
        budget_alert(50.00, 5.00)  # 10 days left
        
        # Verify no message was sent
        mock_send_message.assert_not_called()
    
    def test_smart_send_message_test_mode(self):
        """Test smart send message in test mode"""
        os.environ['REMINDER_TEST_MODE'] = 'true'
        
        with patch('builtins.print') as mock_print:
            result = smart_send_message("Test message")
        
        # Verify test mode behavior
        self.assertTrue(result['sent'])
        self.assertEqual(result['method'], 'test_console')
        self.assertTrue(result['test_mode'])
        mock_print.assert_called_with("[TEST MODE] Would send message: Test message")
    
    def test_smart_send_message_console_mode(self):
        """Test smart send message in console mode"""
        os.environ['REMINDER_DELIVERY_METHOD'] = 'console'
        os.environ['REMINDER_TEST_MODE'] = 'false'
        
        with patch('builtins.print') as mock_print:
            result = smart_send_message("Console test message")
        
        # Verify console mode behavior
        self.assertTrue(result['sent'])
        self.assertEqual(result['method'], 'console')
        mock_print.assert_called_with("[REMINDER] Console test message")
    
    @patch('twilio_sender.send_sms')
    def test_smart_send_message_sms_success(self, mock_send_sms):
        """Test smart send message SMS mode success"""
        os.environ['REMINDER_DELIVERY_METHOD'] = 'sms'
        os.environ['REMINDER_TEST_MODE'] = 'false'
        mock_send_sms.return_value = True
        
        result = smart_send_message("SMS test message")
        
        # Verify SMS was attempted and succeeded
        self.assertTrue(result['sent'])
        self.assertEqual(result['method'], 'sms')
        mock_send_sms.assert_called_once_with("SMS test message", None)
        self.assertEqual(len(result['attempts']), 1)
        self.assertTrue(result['attempts'][0]['success'])
    
    @patch('twilio_sender.send_sms')
    @patch('builtins.print')
    def test_smart_send_message_sms_fallback_to_console(self, mock_print, mock_send_sms):
        """Test smart send message SMS failure with console fallback"""
        os.environ['REMINDER_DELIVERY_METHOD'] = 'sms'
        os.environ['REMINDER_ENABLE_FALLBACK'] = 'true'
        os.environ['REMINDER_TEST_MODE'] = 'false'
        mock_send_sms.return_value = False
        
        result = smart_send_message("Fallback test message")
        
        # Should try SMS first, then fallback to console
        self.assertTrue(result['sent'])
        self.assertEqual(result['method'], 'console_fallback')
        mock_send_sms.assert_called_once()
        mock_print.assert_called_with("[FALLBACK REMINDER] Fallback test message")
        
        # Should have attempts for SMS, WhatsApp (fallback), and console (final fallback)
        self.assertGreaterEqual(len(result['attempts']), 2)
        self.assertFalse(result['attempts'][0]['success'])  # SMS failed
        self.assertTrue(result['attempts'][-1]['success'])  # Final attempt (console) succeeded
    
    @patch('twilio_sender.send_message')
    @patch('twilio_sender.send_sms')
    def test_smart_send_message_both_method(self, mock_send_sms, mock_send_message):
        """Test smart send message with 'both' method"""
        os.environ['REMINDER_DELIVERY_METHOD'] = 'both'
        os.environ['REMINDER_TEST_MODE'] = 'false'
        
        # WhatsApp succeeds, SMS shouldn't be called
        mock_send_message.return_value = True
        
        result = smart_send_message("Both method test")
        
        # Should try WhatsApp first and succeed
        self.assertTrue(result['sent'])
        self.assertEqual(result['method'], 'whatsapp')
        mock_send_message.assert_called_once_with("Both method test", None)
        mock_send_sms.assert_not_called()  # Shouldn't fallback to SMS
    
    def test_smart_send_message_unknown_method_fallback(self):
        """Test smart send message with unknown delivery method"""
        os.environ['REMINDER_DELIVERY_METHOD'] = 'unknown_method'
        os.environ['REMINDER_TEST_MODE'] = 'false'
        
        with patch('builtins.print') as mock_print:
            result = smart_send_message("Unknown method test")
        
        # Should fallback to console
        self.assertTrue(result['sent'])
        self.assertEqual(result['method'], 'console_fallback')
        mock_print.assert_called_with("[REMINDER] Unknown method test")


class TestIntegrationMocked(unittest.TestCase):
    """Integration tests with proper mocking"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_env_vars = {
            'TWILIO_ACCOUNT_SID': 'test_account_sid',
            'TWILIO_AUTH_TOKEN': 'test_auth_token',
            'TWILIO_FROM_NUMBER': '+1234567890',
            'TWILIO_TO_NUMBER': '+0987654321',
        }
        
        for key, value in self.test_env_vars.items():
            os.environ[key] = value
    
    def tearDown(self):
        """Clean up"""
        for key in self.test_env_vars.keys():
            os.environ.pop(key, None)
        
        # Clean up delivery method env vars
        for key in ['REMINDER_DELIVERY_METHOD', 'REMINDER_TEST_MODE', 'REMINDER_ENABLE_FALLBACK']:
            os.environ.pop(key, None)
    
    @patch('twilio_sender.Client')
    def test_full_delivery_pipeline(self, mock_client_class):
        """Test the full delivery pipeline with mocked Twilio"""
        # Set up successful Twilio mock
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.sid = 'pipeline_test_sid'
        mock_client.messages.create.return_value = mock_message
        mock_client_class.return_value = mock_client
        
        # Test various delivery scenarios
        test_cases = [
            ('sms', 'SMS pipeline test', 'sms'),
            ('whatsapp', 'WhatsApp pipeline test', 'whatsapp'),
            ('console', 'Console pipeline test', 'console'),
        ]
        
        for method, message, expected_method in test_cases:
            with self.subTest(method=method):
                os.environ['REMINDER_DELIVERY_METHOD'] = method
                os.environ['REMINDER_TEST_MODE'] = 'false'
                
                if method == 'console':
                    with patch('builtins.print') as mock_print:
                        result = smart_send_message(message)
                        mock_print.assert_called_with(f"[REMINDER] {message}")
                else:
                    result = smart_send_message(message)
                
                self.assertTrue(result['sent'])
                self.assertEqual(result['method'], expected_method)


def run_mocked_tests():
    """Run all mocked SMS tests"""
    print("🧪 Running Mocked SMS Test Suite")
    print("=" * 50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSMSMocked))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationMocked))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Mocked SMS Test Results")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"  • {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n💥 ERRORS:")
        for test, traceback in result.errors:
            print(f"  • {test}: {traceback.split('Exception:')[-1].strip()}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    if success:
        print("\n✅ All mocked SMS tests passed!")
        print("💬 SMS functionality can be tested safely without sending real messages")
    else:
        print(f"\n⚠️ {len(result.failures) + len(result.errors)} test(s) failed")
    
    return success


if __name__ == "__main__":
    success = run_mocked_tests()
    exit(0 if success else 1)