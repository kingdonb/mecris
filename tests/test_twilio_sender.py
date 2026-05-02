"""
Unit tests for twilio_sender.py

twilio and dotenv are not installed in CI; they are injected into sys.modules as
MagicMocks at module level before twilio_sender is imported. Same bootstrap pattern
used by test_fetch_groq_usage.py and test_mcp_bridge.py.

Coverage:
  - send_sms()                  — always False (A2P disabled)
  - send_whatsapp_template()    — missing creds, missing final_to, success (prefix
                                   added / preserved), user_id resolve, encrypt
                                   decrypt success/failure, outer exception
  - send_message()              — missing creds, success (prefix added / preserved),
                                   user_id decrypt success/failure, outer exception,
                                   default from_number
  - smart_send_message()        — console default, whatsapp template success,
                                   template-fail→freeform, both-fail→console,
                                   freeform without template SID, template pool
                                   SID override, vacation_mode flag, temp regex,
                                   mecris_daily_alert_v1 field order, message with
                                   no key:value pairs (defaults)

Total: 25 tests
"""

import json
import os
import sys
import pytest
from unittest.mock import MagicMock, patch, mock_open

# ---------------------------------------------------------------------------
# Bootstrap unavailable optional deps before twilio_sender is imported
# ---------------------------------------------------------------------------

_mock_twilio_rest = MagicMock()
_mock_twilio_rest.Client = MagicMock()

_mock_dotenv = MagicMock()
_mock_usage_tracker = MagicMock()
_mock_services = MagicMock()
_mock_enc_service_mod = MagicMock()

sys.modules.setdefault("twilio", MagicMock())
sys.modules.setdefault("twilio.rest", _mock_twilio_rest)
sys.modules.setdefault("dotenv", _mock_dotenv)
sys.modules.setdefault("usage_tracker", _mock_usage_tracker)
sys.modules.setdefault("services", _mock_services)
sys.modules.setdefault("services.encryption_service", _mock_enc_service_mod)

import twilio_sender  # noqa: E402 — must be after sys.modules bootstrap
from twilio_sender import (  # noqa: E402
    send_sms,
    send_whatsapp_template,
    send_message,
    smart_send_message,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Standard env with all required Twilio credentials
_CREDS = {
    "TWILIO_ACCOUNT_SID": "AC123",
    "TWILIO_AUTH_TOKEN": "auth_token_abc",
    "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
    "TWILIO_TO_NUMBER": "+1234567890",
}


def _mock_client(sid="SM_test_sid"):
    """Return (mock_Client_class, mock_client_instance) with messages.create pre-configured."""
    inst = MagicMock()
    inst.messages.create.return_value = MagicMock(sid=sid)
    cls = MagicMock(return_value=inst)
    return cls, inst


def _tracker_module(prefs=None):
    """Return a fake usage_tracker sys.module entry whose get_tracker() returns prefs."""
    tracker = MagicMock()
    tracker.get_user_preferences.return_value = prefs or {}
    return MagicMock(get_tracker=MagicMock(return_value=tracker))


def _enc_module(decrypted_phone="+19998887777", fail=False):
    """Return a fake services.encryption_service sys.module entry."""
    enc = MagicMock()
    if fail:
        enc.decrypt.side_effect = Exception("decrypt error")
    else:
        enc.decrypt.return_value = decrypted_phone
    return MagicMock(EncryptionService=MagicMock(return_value=enc))


# ---------------------------------------------------------------------------
# TestSendSms
# ---------------------------------------------------------------------------

class TestSendSms:
    def test_returns_false_no_args(self):
        assert send_sms("hello") is False

    def test_returns_false_with_number(self):
        assert send_sms("hello", to_number="+15550001234") is False


# ---------------------------------------------------------------------------
# TestSendWhatsappTemplate
# ---------------------------------------------------------------------------

class TestSendWhatsappTemplate:

    def test_missing_account_sid_returns_false(self):
        env = {k: v for k, v in _CREDS.items() if k != "TWILIO_ACCOUNT_SID"}
        with patch.dict(os.environ, env, clear=True):
            assert send_whatsapp_template("HX123", {"1": "a"}, to_number="+1111") is False

    def test_missing_to_number_and_no_env_fallback_returns_false(self):
        """No to_number, no TWILIO_TO_NUMBER, no user_id — final_to is None → False."""
        env = {k: v for k, v in _CREDS.items() if k != "TWILIO_TO_NUMBER"}
        with patch.dict(os.environ, env, clear=True):
            assert send_whatsapp_template("HX123", {"1": "a"}) is False

    def test_success_adds_whatsapp_prefix(self):
        mock_cls, inst = _mock_client()
        with patch.dict(os.environ, _CREDS, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                result = send_whatsapp_template("HX123", {"1": "a"}, to_number="+1111")
        assert result is True
        assert inst.messages.create.call_args[1]["to"] == "whatsapp:+1111"

    def test_success_preserves_existing_whatsapp_prefix(self):
        mock_cls, inst = _mock_client()
        with patch.dict(os.environ, _CREDS, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                result = send_whatsapp_template("HX123", {"1": "a"}, to_number="whatsapp:+1111")
        assert result is True
        assert inst.messages.create.call_args[1]["to"] == "whatsapp:+1111"

    def test_user_id_no_enc_phone_falls_back_to_env(self):
        mock_cls, inst = _mock_client()
        tracker_mod = _tracker_module(prefs={"phone_number_encrypted": None})
        with patch.dict(os.environ, _CREDS, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                with patch.dict(sys.modules, {"usage_tracker": tracker_mod}):
                    result = send_whatsapp_template("HX123", {"1": "a"}, user_id="u1")
        assert result is True
        assert inst.messages.create.call_args[1]["to"] == "whatsapp:+1234567890"

    def test_user_id_decrypts_encrypted_phone(self):
        mock_cls, inst = _mock_client()
        tracker_mod = _tracker_module(prefs={"phone_number_encrypted": "enc_blob"})
        enc_mod = _enc_module(decrypted_phone="+19998887777")
        with patch.dict(os.environ, _CREDS, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                with patch.dict(sys.modules, {
                    "usage_tracker": tracker_mod,
                    "services.encryption_service": enc_mod,
                }):
                    result = send_whatsapp_template("HX123", {"1": "a"}, user_id="u1")
        assert result is True
        assert inst.messages.create.call_args[1]["to"] == "whatsapp:+19998887777"

    def test_user_id_decrypt_failure_falls_back_to_env(self):
        mock_cls, inst = _mock_client()
        tracker_mod = _tracker_module(prefs={"phone_number_encrypted": "enc_blob"})
        enc_mod = _enc_module(fail=True)
        with patch.dict(os.environ, _CREDS, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                with patch.dict(sys.modules, {
                    "usage_tracker": tracker_mod,
                    "services.encryption_service": enc_mod,
                }):
                    result = send_whatsapp_template("HX123", {"1": "a"}, user_id="u1")
        # Falls back to TWILIO_TO_NUMBER
        assert result is True

    def test_client_exception_returns_false(self):
        mock_cls = MagicMock(side_effect=Exception("Twilio error"))
        with patch.dict(os.environ, _CREDS, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                assert send_whatsapp_template("HX123", {"1": "a"}, to_number="+1111") is False


# ---------------------------------------------------------------------------
# TestSendMessage
# ---------------------------------------------------------------------------

class TestSendMessage:

    def test_missing_credentials_returns_false(self):
        with patch.dict(os.environ, {}, clear=True):
            assert send_message("hello", to_number="+1111") is False

    def test_success_adds_whatsapp_prefix(self):
        mock_cls, inst = _mock_client()
        with patch.dict(os.environ, _CREDS, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                result = send_message("hello", to_number="+1111")
        assert result is True
        assert inst.messages.create.call_args[1]["to"] == "whatsapp:+1111"

    def test_success_preserves_whatsapp_prefix(self):
        mock_cls, inst = _mock_client()
        with patch.dict(os.environ, _CREDS, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                result = send_message("hello", to_number="whatsapp:+1111")
        assert result is True
        assert inst.messages.create.call_args[1]["to"] == "whatsapp:+1111"

    def test_user_id_decrypts_phone(self):
        mock_cls, inst = _mock_client()
        tracker_mod = _tracker_module(prefs={"phone_number_encrypted": "enc_blob"})
        enc_mod = _enc_module(decrypted_phone="+19998887777")
        with patch.dict(os.environ, _CREDS, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                with patch.dict(sys.modules, {
                    "usage_tracker": tracker_mod,
                    "services.encryption_service": enc_mod,
                }):
                    result = send_message("hello", user_id="u1")
        assert result is True
        assert inst.messages.create.call_args[1]["to"] == "whatsapp:+19998887777"

    def test_user_id_decrypt_failure_falls_back_to_env(self):
        mock_cls, inst = _mock_client()
        tracker_mod = _tracker_module(prefs={"phone_number_encrypted": "enc_blob"})
        enc_mod = _enc_module(fail=True)
        with patch.dict(os.environ, _CREDS, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                with patch.dict(sys.modules, {
                    "usage_tracker": tracker_mod,
                    "services.encryption_service": enc_mod,
                }):
                    result = send_message("hello", user_id="u1")
        assert result is True  # uses TWILIO_TO_NUMBER fallback

    def test_client_exception_returns_false(self):
        mock_cls = MagicMock(side_effect=Exception("Twilio error"))
        with patch.dict(os.environ, _CREDS, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                assert send_message("hello", to_number="+1111") is False

    def test_default_from_number_when_env_absent(self):
        """TWILIO_WHATSAPP_FROM defaults to 'whatsapp:+14155238886' when unset."""
        mock_cls, inst = _mock_client()
        env = {k: v for k, v in _CREDS.items() if k != "TWILIO_WHATSAPP_FROM"}
        with patch.dict(os.environ, env, clear=True):
            with patch("twilio_sender.Client", mock_cls):
                result = send_message("hello", to_number="+1111")
        assert result is True
        assert inst.messages.create.call_args[1]["from_"] == "whatsapp:+14155238886"


# ---------------------------------------------------------------------------
# TestSmartSendMessage
# ---------------------------------------------------------------------------

class TestSmartSendMessage:

    def test_console_delivery_default(self):
        """No REMINDER_DELIVERY_METHOD → defaults to console."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(sys.modules, {"usage_tracker": _tracker_module()}):
                with patch("os.path.exists", return_value=False):
                    with patch("builtins.print") as mock_print:
                        result = smart_send_message("Test message")
        assert result["sent"] is True
        assert result["method"] == "console"
        mock_print.assert_called_once_with("[NARRATOR] Test message")

    def test_whatsapp_template_success(self):
        """delivery=whatsapp + content_sid → template send returns True."""
        env = {**_CREDS, "REMINDER_DELIVERY_METHOD": "whatsapp",
               "TWILIO_WHATSAPP_TEMPLATE_SID": "HX999"}
        mock_cls, inst = _mock_client()
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(sys.modules, {"usage_tracker": _tracker_module()}):
                with patch("os.path.exists", return_value=False):
                    with patch("twilio_sender.Client", mock_cls):
                        result = smart_send_message("Goal: 1000\nSteps: 500",
                                                    to_number="+1111")
        assert result["sent"] is True
        assert result["method"] == "whatsapp_template"
        assert result["template_sid"] == "HX999"

    def test_template_fail_freeform_succeeds(self):
        """Template send raises → falls back to freeform WhatsApp."""
        env = {**_CREDS, "REMINDER_DELIVERY_METHOD": "whatsapp",
               "TWILIO_WHATSAPP_TEMPLATE_SID": "HX999"}
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("template error")
            return MagicMock(sid="SM_freeform")

        mock_cls = MagicMock()
        mock_cls.return_value.messages.create.side_effect = side_effect
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(sys.modules, {"usage_tracker": _tracker_module()}):
                with patch("os.path.exists", return_value=False):
                    with patch("twilio_sender.Client", mock_cls):
                        result = smart_send_message("Goal: 1000", to_number="+1111")
        assert result["sent"] is True
        assert result["method"] == "whatsapp_freeform"

    def test_both_whatsapp_fail_console_fallback(self):
        """Template + freeform both fail → console fallback."""
        env = {**_CREDS, "REMINDER_DELIVERY_METHOD": "whatsapp",
               "TWILIO_WHATSAPP_TEMPLATE_SID": "HX999"}
        mock_cls = MagicMock(side_effect=Exception("Twilio down"))
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(sys.modules, {"usage_tracker": _tracker_module()}):
                with patch("os.path.exists", return_value=False):
                    with patch("twilio_sender.Client", mock_cls):
                        with patch("builtins.print"):
                            result = smart_send_message("Goal: 1000", to_number="+1111")
        assert result["sent"] is True
        assert result["method"] == "console"

    def test_whatsapp_no_template_sid_goes_to_freeform(self):
        """delivery=whatsapp but no SID → skips template, goes to freeform."""
        env = {**_CREDS, "REMINDER_DELIVERY_METHOD": "whatsapp"}
        mock_cls, inst = _mock_client()
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(sys.modules, {"usage_tracker": _tracker_module()}):
                with patch("os.path.exists", return_value=False):
                    with patch("twilio_sender.Client", mock_cls):
                        result = smart_send_message("hello", to_number="+1111")
        assert result["sent"] is True
        assert result["method"] == "whatsapp_freeform"

    def test_template_pool_overrides_unknown_sid(self):
        """Pool file replaces unrecognised SID with first approved SID."""
        pool = json.dumps({
            "approved_sids": ["HX_approved"],
            "approved_templates": {"HX_approved": "mecris_status_v2"},
        })
        env = {**_CREDS, "REMINDER_DELIVERY_METHOD": "whatsapp",
               "TWILIO_WHATSAPP_TEMPLATE_SID": "HX_unknown"}
        mock_cls, inst = _mock_client()
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(sys.modules, {"usage_tracker": _tracker_module()}):
                with patch("os.path.exists", return_value=True):
                    with patch("builtins.open", mock_open(read_data=pool)):
                        with patch("twilio_sender.Client", mock_cls):
                            result = smart_send_message("Goal: 1000\nSteps: 500",
                                                        to_number="+1111")
        assert result["sent"] is True
        assert result["template_sid"] == "HX_approved"

    def test_vacation_mode_from_notification_prefs(self):
        """vacation_mode=True in prefs → v5='Vacation' in template variables."""
        env = {**_CREDS, "REMINDER_DELIVERY_METHOD": "whatsapp",
               "TWILIO_WHATSAPP_TEMPLATE_SID": "HX999"}
        prefs = {"notification_prefs": {"vacation_mode": True}}
        mock_cls, inst = _mock_client()
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(sys.modules, {"usage_tracker": _tracker_module(prefs=prefs)}):
                with patch("os.path.exists", return_value=False):
                    with patch("twilio_sender.Client", mock_cls):
                        result = smart_send_message("Goal: 1000", to_number="+1111",
                                                    user_id="u1")
        assert result["sent"] is True
        variables = json.loads(inst.messages.create.call_args[1]["content_variables"])
        # Fallback template (name="unknown"): variables["5"] = v5 = "Vacation"
        assert variables["5"] == "Vacation"

    def test_temp_regex_extracted_from_message(self):
        """Temperature pattern \\d+F in message populates v5."""
        env = {**_CREDS, "REMINDER_DELIVERY_METHOD": "whatsapp",
               "TWILIO_WHATSAPP_TEMPLATE_SID": "HX999"}
        mock_cls, inst = _mock_client()
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(sys.modules, {"usage_tracker": _tracker_module()}):
                with patch("os.path.exists", return_value=False):
                    with patch("twilio_sender.Client", mock_cls):
                        result = smart_send_message("Walk: Done\nSteps: 8000 72F",
                                                    to_number="+1111")
        assert result["sent"] is True
        variables = json.loads(inst.messages.create.call_args[1]["content_variables"])
        assert variables["5"] == "72"

    def test_daily_alert_v1_field_order(self):
        """mecris_daily_alert_v1 maps: {1:v1, 2:v3, 3:v5, 4:v2, 5:v4}."""
        pool = json.dumps({
            "approved_sids": ["HX_daily"],
            "approved_templates": {"HX_daily": "mecris_daily_alert_v1"},
        })
        env = {**_CREDS, "REMINDER_DELIVERY_METHOD": "whatsapp",
               "TWILIO_WHATSAPP_TEMPLATE_SID": "HX_daily"}
        mock_cls, inst = _mock_client()
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(sys.modules, {"usage_tracker": _tracker_module()}):
                with patch("os.path.exists", return_value=True):
                    with patch("builtins.open", mock_open(read_data=pool)):
                        with patch("twilio_sender.Client", mock_cls):
                            # pairs: v1="Steps", v2="1000", v3="Goal", v4="10000"
                            result = smart_send_message("Steps: 1000\nGoal: 10000",
                                                        to_number="+1111")
        assert result["sent"] is True
        variables = json.loads(inst.messages.create.call_args[1]["content_variables"])
        # {1: v1, 2: v3, 3: v5, 4: v2, 5: v4}
        assert variables["1"] == "Steps"
        assert variables["2"] == "Goal"
        assert variables["4"] == "1000"
        assert variables["5"] == "10000"

    def test_message_no_colon_pairs_uses_defaults(self):
        """Message with no key:value lines → all template vars use defaults."""
        env = {**_CREDS, "REMINDER_DELIVERY_METHOD": "whatsapp",
               "TWILIO_WHATSAPP_TEMPLATE_SID": "HX999"}
        mock_cls, inst = _mock_client()
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(sys.modules, {"usage_tracker": _tracker_module()}):
                with patch("os.path.exists", return_value=False):
                    with patch("twilio_sender.Client", mock_cls):
                        result = smart_send_message("No structure whatsoever",
                                                    to_number="+1111")
        assert result["sent"] is True
        variables = json.loads(inst.messages.create.call_args[1]["content_variables"])
        assert variables["1"] == "Activity"  # default v1
        assert variables["2"] == "Pending"   # default v2
