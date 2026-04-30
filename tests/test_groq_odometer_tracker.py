"""
Unit tests for groq_odometer_tracker.py

Uses GroqOdometerTracker.__new__ to bypass __init__ (avoids NEON_DB_URL check
and init_database call). Pattern established in test_billing_reconciliation.py.
"""

import sys
import os
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, call
from dataclasses import fields


# ---------------------------------------------------------------------------
# Module-level import helpers
# ---------------------------------------------------------------------------

def _make_tracker(neon_url="postgresql://fake/db", user_id="test_user"):
    """Build a GroqOdometerTracker instance bypassing __init__."""
    from groq_odometer_tracker import GroqOdometerTracker
    t = GroqOdometerTracker.__new__(GroqOdometerTracker)
    t.neon_url = neon_url
    t.user_id = user_id
    return t


# ---------------------------------------------------------------------------
# OdometerStatus enum
# ---------------------------------------------------------------------------

class TestOdometerStatus:
    def test_all_values_present(self):
        from groq_odometer_tracker import OdometerStatus
        values = {s.value for s in OdometerStatus}
        assert values == {"normal", "approaching", "needs_reading", "reset_detected", "stale"}

    def test_normal_is_default_status_name(self):
        from groq_odometer_tracker import OdometerStatus
        assert OdometerStatus.NORMAL.value == "normal"

    def test_approaching_reset_value(self):
        from groq_odometer_tracker import OdometerStatus
        assert OdometerStatus.APPROACHING_RESET.value == "approaching"


# ---------------------------------------------------------------------------
# OdometerReading dataclass
# ---------------------------------------------------------------------------

class TestOdometerReading:
    def test_required_fields(self):
        from groq_odometer_tracker import OdometerReading
        r = OdometerReading(timestamp="2026-04-01T00:00:00", month="2026-04", value=12.5, is_final=False)
        assert r.timestamp == "2026-04-01T00:00:00"
        assert r.month == "2026-04"
        assert r.value == 12.5
        assert r.is_final is False
        assert r.notes == ""  # default

    def test_notes_can_be_set(self):
        from groq_odometer_tracker import OdometerReading
        r = OdometerReading(timestamp="t", month="2026-04", value=1.0, is_final=True, notes="hello")
        assert r.notes == "hello"

    def test_is_final_true(self):
        from groq_odometer_tracker import OdometerReading
        r = OdometerReading(timestamp="t", month="2026-04", value=5.0, is_final=True)
        assert r.is_final is True


# ---------------------------------------------------------------------------
# _calculate_daily_usage — pure math
# ---------------------------------------------------------------------------

class TestCalculateDailyUsage:
    def test_mid_month_divides_by_day(self):
        t = _make_tracker()
        fixed = datetime(2026, 4, 15)  # day 15
        with patch("groq_odometer_tracker.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            result = t._calculate_daily_usage("2026-04", 30.0)
        assert result == pytest.approx(2.0)  # 30 / 15

    def test_first_day_of_month(self):
        t = _make_tracker()
        fixed = datetime(2026, 4, 1)
        with patch("groq_odometer_tracker.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            result = t._calculate_daily_usage("2026-04", 5.0)
        assert result == pytest.approx(5.0)

    def test_zero_value(self):
        t = _make_tracker()
        fixed = datetime(2026, 4, 10)
        with patch("groq_odometer_tracker.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            result = t._calculate_daily_usage("2026-04", 0.0)
        assert result == 0.0


# ---------------------------------------------------------------------------
# _days_until_month_end — pure date math
# ---------------------------------------------------------------------------

class TestDaysUntilMonthEnd:
    def test_mid_april(self):
        t = _make_tracker()
        # April has 30 days; on the 15th, 15 days left (30-15=15)
        fixed = datetime(2026, 4, 15)
        with patch("groq_odometer_tracker.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            result = t._days_until_month_end()
        assert result == 15

    def test_last_day_of_december(self):
        t = _make_tracker()
        fixed = datetime(2026, 12, 31)
        with patch("groq_odometer_tracker.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            result = t._days_until_month_end()
        assert result == 0

    def test_december_wraps_to_january(self):
        t = _make_tracker()
        fixed = datetime(2026, 12, 1)
        with patch("groq_odometer_tracker.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            result = t._days_until_month_end()
        assert result == 30  # Dec has 31 days; day 1 → 30 remaining

    def test_end_of_month_approaching(self):
        t = _make_tracker()
        fixed = datetime(2026, 4, 28)
        with patch("groq_odometer_tracker.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            result = t._days_until_month_end()
        assert result == 2


# ---------------------------------------------------------------------------
# check_reminder_needs — DB-mocked
# ---------------------------------------------------------------------------

class TestCheckReminderNeeds:
    def _make_mock_conn(self, fetchone_returns=None):
        """Return a mock psycopg2 connection whose cursor.fetchone returns values."""
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = fetchone_returns
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cur

    def test_no_last_reading_returns_needs_reading(self):
        t = _make_tracker()
        mid_month = datetime(2026, 4, 15, 12, 0, 0)
        with patch("groq_odometer_tracker.datetime") as mock_dt, \
             patch.object(t, "get_last_reading", return_value=None), \
             patch.object(t, "resolve_user_id", side_effect=lambda x: x or t.user_id):
            mock_dt.now.return_value = mid_month
            result = t.check_reminder_needs("test_user")
        assert result["status"] == "needs_reading"
        assert any(r["type"] == "initial_reading" for r in result["reminders"])

    def test_stale_reading_over_7_days(self):
        t = _make_tracker()
        now = datetime(2026, 4, 15, 12, 0, 0)
        old_ts = datetime(2026, 4, 5, 12, 0, 0)
        last_reading = {"month": "2026-04", "value": 10.0, "created_at": old_ts.isoformat(), "timestamp": old_ts.isoformat()}
        with patch("groq_odometer_tracker.datetime") as mock_dt, \
             patch.object(t, "get_last_reading", return_value=last_reading), \
             patch.object(t, "resolve_user_id", side_effect=lambda x: x or t.user_id):
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = t.check_reminder_needs("test_user")
        assert result["status"] == "stale"
        assert any(r["type"] == "stale_data" for r in result["reminders"])

    def test_approaching_month_end(self):
        t = _make_tracker()
        # April 28 → 2 days until end
        now = datetime(2026, 4, 28, 12, 0, 0)
        recent_ts = datetime(2026, 4, 27, 12, 0, 0)
        last_reading = {"month": "2026-04", "value": 8.0, "created_at": recent_ts.isoformat(), "timestamp": recent_ts.isoformat()}
        with patch("groq_odometer_tracker.datetime") as mock_dt, \
             patch.object(t, "get_last_reading", return_value=last_reading), \
             patch.object(t, "resolve_user_id", side_effect=lambda x: x or t.user_id):
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = t.check_reminder_needs("test_user")
        assert result["status"] == "approaching"
        assert any(r["type"] == "month_end" for r in result["reminders"])

    def test_normal_status_recent_reading(self):
        t = _make_tracker()
        now = datetime(2026, 4, 15, 12, 0, 0)
        yesterday = datetime(2026, 4, 14, 12, 0, 0)
        last_reading = {"month": "2026-04", "value": 5.0, "created_at": yesterday.isoformat(), "timestamp": yesterday.isoformat()}
        with patch("groq_odometer_tracker.datetime") as mock_dt, \
             patch.object(t, "get_last_reading", return_value=last_reading), \
             patch.object(t, "resolve_user_id", side_effect=lambda x: x or t.user_id):
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            result = t.check_reminder_needs("test_user")
        assert result["status"] == "normal"
        # days_until_reset should be 15 (April 15 → April 30)
        assert result["days_until_reset"] == 15

    def test_no_neon_url_returns_needs_reading(self):
        t = _make_tracker(neon_url=None)
        result = t.check_reminder_needs("test_user")
        assert result["status"] == "needs_reading"


# ---------------------------------------------------------------------------
# get_usage_for_virtual_budget — DB-mocked
# ---------------------------------------------------------------------------

class TestGetUsageForVirtualBudget:
    def test_no_neon_url_returns_error(self):
        t = _make_tracker(neon_url=None)
        result = t.get_usage_for_virtual_budget("test_user")
        assert result["has_data"] is False
        assert "error" in result

    def test_no_current_month_data_returns_needs_reading(self):
        t = _make_tracker()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        with patch("groq_odometer_tracker.psycopg2.connect", return_value=mock_conn), \
             patch.object(t, "resolve_user_id", side_effect=lambda x: x or t.user_id):
            result = t.get_usage_for_virtual_budget("test_user")
        assert result["has_data"] is False
        assert result.get("needs_reading") is True

    def test_with_current_month_data_no_yesterday(self):
        t = _make_tracker()
        now = datetime(2026, 4, 10, 12, 0, 0)
        mock_cur = MagicMock()
        # First fetchone = current month reading (val, ts)
        mock_cur.fetchone.side_effect = [(20.0, now), None]  # no yesterday
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        with patch("groq_odometer_tracker.psycopg2.connect", return_value=mock_conn), \
             patch("groq_odometer_tracker.datetime") as mock_dt, \
             patch.object(t, "resolve_user_id", side_effect=lambda x: x or t.user_id):
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.strptime = datetime.strptime
            result = t.get_usage_for_virtual_budget("test_user")
        assert result["has_data"] is True
        assert result["cumulative_cost"] == 20.0
        assert result["daily_average"] == pytest.approx(2.0)  # 20/10
        # daily_actual falls back to avg when no yesterday
        assert result["daily_actual"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# generate_narrator_context — integration of reminder + usage
# ---------------------------------------------------------------------------

class TestGenerateNarratorContext:
    def test_no_data_shows_needs_action(self):
        t = _make_tracker(neon_url=None)
        with patch.object(t, "resolve_user_id", side_effect=lambda x: x or t.user_id):
            result = t.generate_narrator_context("test_user")
        ctx = result["groq_tracking"]
        assert ctx["has_current_data"] is False
        assert ctx["needs_action"] is True

    def test_with_data_populates_spend(self):
        t = _make_tracker()
        reminder = {"status": "normal", "reminders": [], "days_until_reset": 15, "last_reading_age_days": 1}
        usage = {"has_data": True, "cumulative_cost": 45.0, "daily_average": 3.0}
        with patch.object(t, "check_reminder_needs", return_value=reminder), \
             patch.object(t, "get_usage_for_virtual_budget", return_value=usage), \
             patch.object(t, "resolve_user_id", side_effect=lambda x: x or t.user_id):
            result = t.generate_narrator_context("test_user")
        ctx = result["groq_tracking"]
        assert ctx["current_month_spend"] == 45.0
        assert ctx["daily_average"] == 3.0
        assert ctx["needs_action"] is False

    def test_urgent_reminder_elevated(self):
        t = _make_tracker()
        urgent_msg = "⚠️ Last month not recorded"
        reminder = {
            "status": "approaching",
            "reminders": [{"type": "month_end", "urgency": "high", "message": urgent_msg}],
            "days_until_reset": 1,
            "last_reading_age_days": 1
        }
        usage = {"has_data": False}
        with patch.object(t, "check_reminder_needs", return_value=reminder), \
             patch.object(t, "get_usage_for_virtual_budget", return_value=usage), \
             patch.object(t, "resolve_user_id", side_effect=lambda x: x or t.user_id):
            result = t.generate_narrator_context("test_user")
        ctx = result["groq_tracking"]
        assert ctx["urgent_reminder"] == urgent_msg
        assert ctx["needs_action"] is True
