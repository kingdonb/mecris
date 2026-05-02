"""
Unit tests for scripts/base_walk_reminder.py

Bootstrap pattern: set sys.modules before import to avoid external deps.
"""
import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap — mock all heavy external imports before the module is loaded
# ---------------------------------------------------------------------------
_mock_dotenv = MagicMock()
_mock_twilio_sender = MagicMock()
_mock_beeminder_client = MagicMock()
_mock_usage_tracker = MagicMock()

sys.modules.setdefault("dotenv", _mock_dotenv)
sys.modules.setdefault("twilio_sender", _mock_twilio_sender)
sys.modules.setdefault("beeminder_client", _mock_beeminder_client)
sys.modules.setdefault("usage_tracker", _mock_usage_tracker)

# Force a clean import (handles repeated test runs in the same process)
if "scripts.base_walk_reminder" in sys.modules:
    del sys.modules["scripts.base_walk_reminder"]

import scripts.base_walk_reminder as bwr  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prefs(
    *,
    opted_in: bool = True,
    start: int = 9,
    end: int = 21,
    vacation: bool = False,
) -> dict:
    return {
        "notification_prefs": {
            "sms_opted_in": opted_in,
            "time_window_start": start,
            "time_window_end": end,
            "vacation_mode": vacation,
        }
    }


# ---------------------------------------------------------------------------
# Tests for check_walk_needed()
# ---------------------------------------------------------------------------


class TestCheckWalkNeeded:
    def test_returns_false_when_activity_today(self):
        """If Beeminder reports activity, no walk is needed (returns False)."""
        mock_client = MagicMock()
        mock_client.has_activity_today = AsyncMock(return_value=True)

        with patch.object(bwr, "BeeminderClient", return_value=mock_client):
            result = bwr.check_walk_needed()

        assert result is False

    def test_returns_true_when_no_activity_today(self):
        """If Beeminder reports no activity, a walk is needed (returns True)."""
        mock_client = MagicMock()
        mock_client.has_activity_today = AsyncMock(return_value=False)

        with patch.object(bwr, "BeeminderClient", return_value=mock_client):
            result = bwr.check_walk_needed()

        assert result is True

    def test_fail_safe_on_exception(self):
        """If BeeminderClient raises, fail-safe assumes walk is needed."""
        mock_client = MagicMock()
        mock_client.has_activity_today = AsyncMock(side_effect=RuntimeError("API down"))

        with patch.object(bwr, "BeeminderClient", return_value=mock_client):
            result = bwr.check_walk_needed()

        assert result is True

    def test_fail_safe_on_constructor_error(self):
        """If BeeminderClient() itself raises, fail-safe assumes walk is needed."""
        with patch.object(bwr, "BeeminderClient", side_effect=Exception("creds missing")):
            result = bwr.check_walk_needed()

        assert result is True


# ---------------------------------------------------------------------------
# Tests for run_base_reminder()
# ---------------------------------------------------------------------------


class TestRunBaseReminder:
    def setup_method(self):
        """Reset shared mocks before each test."""
        _mock_twilio_sender.reset_mock()
        _mock_usage_tracker.reset_mock()

    def test_returns_early_if_no_phone_number(self):
        """If TWILIO_TO_NUMBER is absent, function returns without sending."""
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(bwr, "check_walk_needed") as mock_cwn:
                bwr.run_base_reminder()
                mock_cwn.assert_not_called()

    def test_returns_early_if_walk_already_done(self):
        """If check_walk_needed() returns False, no message is sent."""
        with patch.dict("os.environ", {"TWILIO_TO_NUMBER": "+15555550000"}):
            with patch.object(bwr, "check_walk_needed", return_value=False):
                with patch.object(bwr, "smart_send_message") as mock_send:
                    bwr.run_base_reminder()
                    mock_send.assert_not_called()

    def test_returns_early_if_user_not_in_db(self):
        """If tracker.get_user_preferences() returns None, function exits early."""
        mock_tracker = MagicMock()
        mock_tracker.get_user_preferences.return_value = None
        _mock_usage_tracker.get_tracker.return_value = mock_tracker

        with patch.dict("os.environ", {"TWILIO_TO_NUMBER": "+15555550000"}):
            with patch.object(bwr, "check_walk_needed", return_value=True):
                with patch.object(bwr, "smart_send_message") as mock_send:
                    bwr.run_base_reminder()
                    mock_send.assert_not_called()

    def test_returns_early_if_not_opted_in(self):
        """If sms_opted_in is False, no message is sent."""
        mock_tracker = MagicMock()
        mock_tracker.get_user_preferences.return_value = _make_prefs(opted_in=False)
        _mock_usage_tracker.get_tracker.return_value = mock_tracker

        with patch.dict("os.environ", {"TWILIO_TO_NUMBER": "+15555550000"}):
            with patch.object(bwr, "check_walk_needed", return_value=True):
                with patch.object(bwr, "smart_send_message") as mock_send:
                    bwr.run_base_reminder()
                    mock_send.assert_not_called()

    def test_returns_early_if_outside_time_window(self):
        """If current hour is outside the user's time window, no message is sent."""
        # Window 14–17; patch datetime to return hour=9 (outside window)
        mock_tracker = MagicMock()
        mock_tracker.get_user_preferences.return_value = _make_prefs(start=14, end=17)
        _mock_usage_tracker.get_tracker.return_value = mock_tracker

        fake_now = MagicMock()
        fake_now.hour = 9

        with patch.dict("os.environ", {"TWILIO_TO_NUMBER": "+15555550000"}):
            with patch.object(bwr, "check_walk_needed", return_value=True):
                with patch.object(bwr, "datetime") as mock_dt:
                    mock_dt.now.return_value = fake_now
                    with patch.object(bwr, "smart_send_message") as mock_send:
                        bwr.run_base_reminder()
                        mock_send.assert_not_called()

    def test_sends_message_inside_time_window(self):
        """When all compliance checks pass, smart_send_message is called once."""
        mock_tracker = MagicMock()
        mock_tracker.get_user_preferences.return_value = _make_prefs(start=9, end=21)
        _mock_usage_tracker.get_tracker.return_value = mock_tracker

        fake_now = MagicMock()
        fake_now.hour = 14  # inside window

        mock_result = {"sent": True, "method": "sms"}

        with patch.dict("os.environ", {"TWILIO_TO_NUMBER": "+15555550000"}):
            with patch.object(bwr, "check_walk_needed", return_value=True):
                with patch.object(bwr, "datetime") as mock_dt:
                    mock_dt.now.return_value = fake_now
                    with patch.object(bwr, "smart_send_message", return_value=mock_result) as mock_send:
                        bwr.run_base_reminder()
                        mock_send.assert_called_once()
                        call_args = mock_send.call_args
                        assert "+15555550000" in call_args[0]

    def test_vacation_mode_message_content(self):
        """In vacation mode, message uses 'Activity log: Pending'."""
        mock_tracker = MagicMock()
        mock_tracker.get_user_preferences.return_value = _make_prefs(start=9, end=21, vacation=True)
        _mock_usage_tracker.get_tracker.return_value = mock_tracker

        fake_now = MagicMock()
        fake_now.hour = 14

        mock_result = {"sent": True, "method": "sms"}
        captured = {}

        def capture_send(msg, phone):
            captured["msg"] = msg
            return mock_result

        with patch.dict("os.environ", {"TWILIO_TO_NUMBER": "+15555550000"}):
            with patch.object(bwr, "check_walk_needed", return_value=True):
                with patch.object(bwr, "datetime") as mock_dt:
                    mock_dt.now.return_value = fake_now
                    with patch.object(bwr, "smart_send_message", side_effect=capture_send):
                        bwr.run_base_reminder()

        assert "Activity log: Pending" in captured["msg"]
        assert "Physical activity: Pending" not in captured["msg"]

    def test_non_vacation_mode_message_content(self):
        """Outside vacation mode, message uses 'Physical activity: Pending'."""
        mock_tracker = MagicMock()
        mock_tracker.get_user_preferences.return_value = _make_prefs(start=9, end=21, vacation=False)
        _mock_usage_tracker.get_tracker.return_value = mock_tracker

        fake_now = MagicMock()
        fake_now.hour = 14

        mock_result = {"sent": True, "method": "sms"}
        captured = {}

        def capture_send(msg, phone):
            captured["msg"] = msg
            return mock_result

        with patch.dict("os.environ", {"TWILIO_TO_NUMBER": "+15555550000"}):
            with patch.object(bwr, "check_walk_needed", return_value=True):
                with patch.object(bwr, "datetime") as mock_dt:
                    mock_dt.now.return_value = fake_now
                    with patch.object(bwr, "smart_send_message", side_effect=capture_send):
                        bwr.run_base_reminder()

        assert "Physical activity: Pending" in captured["msg"]
        assert "Activity log: Pending" not in captured["msg"]

    def test_logs_error_when_send_fails(self, caplog):
        """If smart_send_message returns sent=False, logs an error."""
        import logging

        mock_tracker = MagicMock()
        mock_tracker.get_user_preferences.return_value = _make_prefs(start=9, end=21)
        _mock_usage_tracker.get_tracker.return_value = mock_tracker

        fake_now = MagicMock()
        fake_now.hour = 14

        mock_result = {"sent": False}

        with patch.dict("os.environ", {"TWILIO_TO_NUMBER": "+15555550000"}):
            with patch.object(bwr, "check_walk_needed", return_value=True):
                with patch.object(bwr, "datetime") as mock_dt:
                    mock_dt.now.return_value = fake_now
                    with patch.object(bwr, "smart_send_message", return_value=mock_result):
                        with caplog.at_level(logging.ERROR, logger="mecris.base_reminder"):
                            bwr.run_base_reminder()

        assert any("Failed to send" in r.message for r in caplog.records)

    def test_window_boundary_at_start_is_inside(self):
        """Time window check is inclusive at start_hour."""
        mock_tracker = MagicMock()
        mock_tracker.get_user_preferences.return_value = _make_prefs(start=14, end=17)
        _mock_usage_tracker.get_tracker.return_value = mock_tracker

        fake_now = MagicMock()
        fake_now.hour = 14  # exactly at start

        mock_result = {"sent": True, "method": "sms"}

        with patch.dict("os.environ", {"TWILIO_TO_NUMBER": "+15555550000"}):
            with patch.object(bwr, "check_walk_needed", return_value=True):
                with patch.object(bwr, "datetime") as mock_dt:
                    mock_dt.now.return_value = fake_now
                    with patch.object(bwr, "smart_send_message", return_value=mock_result) as mock_send:
                        bwr.run_base_reminder()
                        mock_send.assert_called_once()

    def test_window_boundary_at_end_is_inside(self):
        """Time window check is inclusive at end_hour."""
        mock_tracker = MagicMock()
        mock_tracker.get_user_preferences.return_value = _make_prefs(start=14, end=17)
        _mock_usage_tracker.get_tracker.return_value = mock_tracker

        fake_now = MagicMock()
        fake_now.hour = 17  # exactly at end

        mock_result = {"sent": True, "method": "sms"}

        with patch.dict("os.environ", {"TWILIO_TO_NUMBER": "+15555550000"}):
            with patch.object(bwr, "check_walk_needed", return_value=True):
                with patch.object(bwr, "datetime") as mock_dt:
                    mock_dt.now.return_value = fake_now
                    with patch.object(bwr, "smart_send_message", return_value=mock_result) as mock_send:
                        bwr.run_base_reminder()
                        mock_send.assert_called_once()

    def test_message_contains_alert_header(self):
        """Sent message always begins with the approved WhatsApp template header."""
        mock_tracker = MagicMock()
        mock_tracker.get_user_preferences.return_value = _make_prefs(start=9, end=21)
        _mock_usage_tracker.get_tracker.return_value = mock_tracker

        fake_now = MagicMock()
        fake_now.hour = 14

        captured = {}

        def capture_send(msg, phone):
            captured["msg"] = msg
            return {"sent": True, "method": "sms"}

        with patch.dict("os.environ", {"TWILIO_TO_NUMBER": "+15555550000"}):
            with patch.object(bwr, "check_walk_needed", return_value=True):
                with patch.object(bwr, "datetime") as mock_dt:
                    mock_dt.now.return_value = fake_now
                    with patch.object(bwr, "smart_send_message", side_effect=capture_send):
                        bwr.run_base_reminder()

        assert captured["msg"].startswith("Mecris System Alert")
