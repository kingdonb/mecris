"""
Unit tests for SMSConsentManager — yebyen/mecris#164.

Covers: opt_in_user, opt_out_user, can_send_message (all branches),
log_message_sent (history + 30-day trim), get_consent_summary.

All tests use tmp_path to avoid writing to disk.
"""

import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch


def _make_manager(tmp_path):
    """Return a fresh SMSConsentManager backed by a tmp file."""
    from sms_consent_manager import SMSConsentManager
    return SMSConsentManager(data_file=str(tmp_path / "sms_consent.json"))


# ---------------------------------------------------------------------------
# opt_in_user
# ---------------------------------------------------------------------------

class TestOptIn:
    def test_opt_in_returns_consent_record(self, tmp_path):
        mgr = _make_manager(tmp_path)
        record = mgr.opt_in_user("+15550001234", "web")
        assert record["opted_in"] is True
        assert record["opt_in_method"] == "web"
        assert "walk_reminder" in record["message_types"]

    def test_opt_in_custom_message_types(self, tmp_path):
        mgr = _make_manager(tmp_path)
        record = mgr.opt_in_user("+15550001234", "api", ["budget_alert"])
        assert record["message_types"] == ["budget_alert"]

    def test_opt_in_persisted_to_file(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        # Reload from file
        mgr2 = _make_manager(tmp_path)
        prefs = mgr2.get_user_preferences("+15550001234")
        assert prefs is not None
        assert prefs["opted_in"] is True

    def test_opt_in_strips_phone_formatting(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+1-555-000-1234", "web")
        # Should be findable via the cleaned-up key
        assert mgr.get_user_preferences("+1-555-000-1234") is not None


# ---------------------------------------------------------------------------
# opt_out_user
# ---------------------------------------------------------------------------

class TestOptOut:
    def test_opt_out_known_user_returns_true(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        result = mgr.opt_out_user("+15550001234", "sms")
        assert result is True

    def test_opt_out_sets_opted_in_false(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        mgr.opt_out_user("+15550001234")
        prefs = mgr.get_user_preferences("+15550001234")
        assert prefs["opted_in"] is False

    def test_opt_out_unknown_user_returns_false(self, tmp_path):
        mgr = _make_manager(tmp_path)
        result = mgr.opt_out_user("+19990001234")
        assert result is False

    def test_opt_out_records_method(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        mgr.opt_out_user("+15550001234", "support")
        prefs = mgr.get_user_preferences("+15550001234")
        assert prefs["opt_out_method"] == "support"


# ---------------------------------------------------------------------------
# can_send_message
# ---------------------------------------------------------------------------

class TestCanSendMessage:
    def _opted_in_mgr(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        return mgr

    def test_unknown_user_cannot_send(self, tmp_path):
        mgr = _make_manager(tmp_path)
        result = mgr.can_send_message("+19990001234")
        assert result["can_send"] is False
        assert "not found" in result["reason"]

    def test_opted_out_user_cannot_send(self, tmp_path):
        mgr = self._opted_in_mgr(tmp_path)
        mgr.opt_out_user("+15550001234")
        result = mgr.can_send_message("+15550001234")
        assert result["can_send"] is False
        assert "opted out" in result["reason"]

    def test_wrong_message_type_cannot_send(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web", ["budget_alert"])
        result = mgr.can_send_message("+15550001234", "walk_reminder")
        assert result["can_send"] is False
        assert "walk_reminder" in result["reason"]

    def test_within_window_and_under_limit_can_send(self, tmp_path):
        mgr = self._opted_in_mgr(tmp_path)
        # Default window: 14-17; mock hour=15
        with patch("sms_consent_manager.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 4, 12, 15, 0, 0)
            result = mgr.can_send_message("+15550001234", "walk_reminder")
        assert result["can_send"] is True

    def test_outside_time_window_cannot_send(self, tmp_path):
        mgr = self._opted_in_mgr(tmp_path)
        # Hour 8 is before window start (14)
        with patch("sms_consent_manager.datetime") as mock_dt:
            mock_dt.now.side_effect = lambda: datetime(2026, 4, 12, 8, 0, 0)
            result = mgr.can_send_message("+15550001234", "walk_reminder")
        assert result["can_send"] is False
        assert "time window" in result["reason"]

    def test_daily_limit_reached_cannot_send(self, tmp_path):
        mgr = self._opted_in_mgr(tmp_path)
        today = "2026-04-12"
        # Manually stuff history with 3 messages from today
        user_id = "15550001234"
        for _ in range(3):
            mgr.consent_data["users"][user_id]["message_history"].append({
                "timestamp": f"{today}T15:00:00",
                "date": today,
                "message": "test",
                "message_type": "walk_reminder",
                "delivery_method": "sms",
            })
        with patch("sms_consent_manager.datetime") as mock_dt:
            mock_dt.now.side_effect = lambda: datetime(2026, 4, 12, 15, 0, 0)
            result = mgr.can_send_message("+15550001234", "walk_reminder")
        assert result["can_send"] is False
        assert "Daily message limit" in result["reason"]


# ---------------------------------------------------------------------------
# log_message_sent
# ---------------------------------------------------------------------------

class TestLogMessageSent:
    def test_log_adds_to_history(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        result = mgr.log_message_sent("+15550001234", "Go walk the dogs!", "walk_reminder")
        assert result is True
        prefs = mgr.get_user_preferences("+15550001234")
        assert len(prefs["message_history"]) == 1
        assert prefs["message_history"][0]["message_type"] == "walk_reminder"

    def test_log_unknown_user_returns_false(self, tmp_path):
        mgr = _make_manager(tmp_path)
        result = mgr.log_message_sent("+19990001234", "test", "walk_reminder")
        assert result is False

    def test_log_trims_history_older_than_30_days(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        user_id = "15550001234"
        old_date = (datetime.now().date() - timedelta(days=31)).isoformat()
        mgr.consent_data["users"][user_id]["message_history"].append({
            "timestamp": f"{old_date}T10:00:00",
            "date": old_date,
            "message": "old message",
            "message_type": "walk_reminder",
            "delivery_method": "sms",
        })
        # Now log a new message — this triggers trim
        mgr.log_message_sent("+15550001234", "new message", "walk_reminder")
        prefs = mgr.get_user_preferences("+15550001234")
        dates = [m["date"] for m in prefs["message_history"]]
        assert old_date not in dates

    def test_log_keeps_recent_history(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        mgr.log_message_sent("+15550001234", "msg1", "walk_reminder")
        mgr.log_message_sent("+15550001234", "msg2", "budget_alert")
        prefs = mgr.get_user_preferences("+15550001234")
        assert len(prefs["message_history"]) == 2


# ---------------------------------------------------------------------------
# get_consent_summary
# ---------------------------------------------------------------------------

class TestGetConsentSummary:
    def test_empty_summary(self, tmp_path):
        mgr = _make_manager(tmp_path)
        summary = mgr.get_consent_summary()
        assert summary["total_users"] == 0
        assert summary["opted_in"] == 0
        assert summary["opted_out"] == 0

    def test_summary_counts_opted_in_and_out(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001111", "web")
        mgr.opt_in_user("+15550002222", "web")
        mgr.opt_in_user("+15550003333", "web")
        mgr.opt_out_user("+15550003333")
        summary = mgr.get_consent_summary()
        assert summary["total_users"] == 3
        assert summary["opted_in"] == 2
        assert summary["opted_out"] == 1

    def test_summary_message_type_breakdown(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001111", "web", ["walk_reminder", "budget_alert"])
        mgr.opt_in_user("+15550002222", "web", ["walk_reminder"])
        summary = mgr.get_consent_summary()
        breakdown = summary["message_types_breakdown"]
        assert breakdown["walk_reminder"] == 2
        assert breakdown["budget_alert"] == 1

    def test_summary_recent_activity_includes_opt_in(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        summary = mgr.get_consent_summary()
        actions = [a["action"] for a in summary["recent_activity"]]
        assert "opt_in" in actions

    def test_summary_recent_activity_includes_opt_out(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        mgr.opt_out_user("+15550001234")
        summary = mgr.get_consent_summary()
        actions = [a["action"] for a in summary["recent_activity"]]
        assert "opt_out" in actions


# ---------------------------------------------------------------------------
# update_user_preferences
# ---------------------------------------------------------------------------

class TestUpdateUserPreferences:
    def test_update_time_window(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        result = mgr.update_user_preferences("+15550001234", {"time_window_start": 9, "time_window_end": 11})
        assert result is True
        prefs = mgr.get_user_preferences("+15550001234")
        assert prefs["preferences"]["time_window_start"] == 9
        assert prefs["preferences"]["time_window_end"] == 11

    def test_update_unknown_user_returns_false(self, tmp_path):
        mgr = _make_manager(tmp_path)
        result = mgr.update_user_preferences("+19990001234", {"time_window_start": 9})
        assert result is False

    def test_update_preserves_consent_status(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.opt_in_user("+15550001234", "web")
        mgr.update_user_preferences("+15550001234", {"max_messages_per_day": 5})
        prefs = mgr.get_user_preferences("+15550001234")
        assert prefs["opted_in"] is True  # not clobbered
        assert prefs["preferences"]["max_messages_per_day"] == 5
