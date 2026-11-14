"""Logs must not contain phone numbers (kingdonb/mecris#167).

Covers log sites outside twilio_sender (which has its own tests): the phone
verification endpoint and the base walk reminder.
"""

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

PHONE = "+15551234567"
DIGITS = "5551234567"
PREFIX = "+1555"


class _FakeTwilioRestException(Exception):
    def __init__(self):
        self.status, self.code = 400, 21211
        super().__init__(f"HTTP 400 error: The 'To' number {PHONE} is not a valid phone number.")


async def _request_verification(caplog, send_side_effect=None, send_return=True):
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}):
        with patch("psycopg2.connect"):
            import mcp_server
            # mcp_server calls logging.basicConfig(force=True) on import, which strips
            # pytest's capture handler; reattach it so these specs can see the logs.
            logging.getLogger().addHandler(caplog.handler)
            send = MagicMock(side_effect=send_side_effect, return_value=send_return)
            with patch("twilio_sender.send_whatsapp_template", send):
                return await mcp_server.request_phone_verification_endpoint({"phone_number": PHONE}, user_id="test-user")


@pytest.mark.asyncio
async def test_verification_success_log_has_no_phone(caplog):
    with caplog.at_level("INFO"):
        await _request_verification(caplog)
    assert PREFIX not in caplog.text
    assert DIGITS not in caplog.text


@pytest.mark.asyncio
async def test_verification_send_exception_log_has_no_phone(caplog):
    with caplog.at_level("INFO"):
        await _request_verification(caplog, send_side_effect=_FakeTwilioRestException())
    assert DIGITS not in caplog.text
    assert "code=21211" in caplog.text


def test_base_walk_reminder_logs_have_no_phone(caplog):
    import scripts.base_walk_reminder as bwr
    tracker = MagicMock()
    tracker.get_user_preferences.return_value = None
    with patch.dict("os.environ", {"TWILIO_TO_NUMBER": PHONE}), \
         patch.object(bwr, "check_walk_needed", return_value=True), \
         patch("usage_tracker.get_tracker", return_value=tracker), \
         caplog.at_level("INFO"):
        bwr.run_base_reminder()
    assert DIGITS not in caplog.text
