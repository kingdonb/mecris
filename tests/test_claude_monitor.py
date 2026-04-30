"""
Unit tests for claude_monitor.py

Covers:
  - ClaudeMonitor._calculate_daily_burn: pure sync logic, no I/O
  - ClaudeMonitor._days_until_expiry: expiry_date config, clamps to 0
  - CreditUsage.to_dict: dataclass serialization
  - BudgetAlert: dataclass field defaults
  - ClaudeMonitor.get_usage_summary: status emoji thresholds (async, mocked)

No live API calls, no Neon, no Twilio — all external I/O is mocked or bypassed.

Refs: yebyen/mecris#306
"""

import asyncio
import sys
import types
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub out twilio so claude_monitor.py can be imported without the package
_twilio_rest = types.ModuleType("twilio.rest")
_twilio_rest.Client = MagicMock()
sys.modules.setdefault("twilio", types.ModuleType("twilio"))
sys.modules.setdefault("twilio.rest", _twilio_rest)

from claude_monitor import BudgetAlert, ClaudeMonitor, CreditUsage  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_monitor(expiry_date="2099-12-31", budget=25.0):
    """Build a ClaudeMonitor via __new__, bypassing __init__ to avoid env deps."""
    m = ClaudeMonitor.__new__(ClaudeMonitor)
    m.api_key = None
    m.usage_file = "/tmp/test_claude_monitor_usage.json"
    m.budget_limit = budget
    m.expiry_date = expiry_date
    m.alerts = []
    m.client = MagicMock()
    return m


def _entry(ts: datetime, credits_remaining: float) -> dict:
    return {
        "timestamp": ts.isoformat(),
        "credits_remaining": credits_remaining,
        "credits_used": 0.0,
        "session_cost": 0.0,
        "daily_burn": 0.0,
        "days_remaining": 0.0,
    }


def _make_usage(days_remaining: float, credits_used=5.0, credits_remaining=20.0) -> CreditUsage:
    return CreditUsage(
        timestamp=datetime.now(),
        credits_used=credits_used,
        credits_remaining=credits_remaining,
        session_cost=0.0,
        daily_burn=1.0,
        days_remaining=days_remaining,
    )


# ---------------------------------------------------------------------------
# _calculate_daily_burn
# ---------------------------------------------------------------------------

class TestCalculateDailyBurn:

    def test_empty_history_returns_zero(self):
        assert _make_monitor()._calculate_daily_burn([]) == 0.0

    def test_single_entry_returns_zero(self):
        history = [_entry(datetime.now(), 20.0)]
        assert _make_monitor()._calculate_daily_burn(history) == 0.0

    def test_two_entries_same_timestamp_returns_zero(self):
        now = datetime.now()
        history = [_entry(now, 20.0), _entry(now, 18.0)]
        assert _make_monitor()._calculate_daily_burn(history) == 0.0

    def test_two_entries_one_day_apart(self):
        t0 = datetime(2026, 1, 1)
        history = [_entry(t0, 20.0), _entry(t0 + timedelta(days=1), 18.0)]
        result = _make_monitor()._calculate_daily_burn(history)
        assert abs(result - 2.0) < 0.01

    def test_two_entries_two_days_apart(self):
        t0 = datetime(2026, 1, 1)
        history = [_entry(t0, 20.0), _entry(t0 + timedelta(days=2), 14.0)]
        result = _make_monitor()._calculate_daily_burn(history)
        assert abs(result - 3.0) < 0.01

    def test_credits_increased_clamped_to_zero(self):
        """Negative burn (credits added) must clamp to 0."""
        t0 = datetime(2026, 1, 1)
        history = [_entry(t0, 15.0), _entry(t0 + timedelta(days=1), 20.0)]
        assert _make_monitor()._calculate_daily_burn(history) == 0.0

    def test_uses_last_seven_of_eight_entries(self):
        """With 8 entries the first is excluded; only the last 7 are used."""
        base = datetime(2026, 1, 1)
        # entry[0] (day 0, 100 credits) is the old one to be excluded
        # entry[1] (day 1, 20 credits) → entry[7] (day 7, 14 credits): 6 burned / 6 days = 1.0/day
        history = [_entry(base, 100.0)] + [
            _entry(base + timedelta(days=i), 21.0 - i)
            for i in range(1, 8)
        ]
        result = _make_monitor()._calculate_daily_burn(history)
        assert abs(result - 1.0) < 0.01

    def test_exactly_seven_entries(self):
        """7 entries → all 7 used; 21→15 over 6 days = 1.0/day."""
        base = datetime(2026, 3, 1)
        history = [_entry(base + timedelta(days=i), 21.0 - i) for i in range(7)]
        result = _make_monitor()._calculate_daily_burn(history)
        assert abs(result - 1.0) < 0.01

    def test_malformed_timestamp_returns_zero(self):
        history = [
            {"timestamp": "NOT-A-DATE", "credits_remaining": 20.0},
            {"timestamp": "ALSO-BAD",   "credits_remaining": 18.0},
        ]
        assert _make_monitor()._calculate_daily_burn(history) == 0.0


# ---------------------------------------------------------------------------
# _days_until_expiry
# ---------------------------------------------------------------------------

class TestDaysUntilExpiry:

    def test_past_date_returns_zero(self):
        assert _make_monitor(expiry_date="2000-01-01")._days_until_expiry() == 0.0

    def test_far_future_returns_large_value(self):
        result = _make_monitor(expiry_date="2099-12-31")._days_until_expiry()
        assert result > 365 * 50

    def test_invalid_format_returns_zero(self):
        assert _make_monitor(expiry_date="not-a-date")._days_until_expiry() == 0.0

    def test_tomorrow_is_approximately_one_day(self):
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        result = _make_monitor(expiry_date=tomorrow)._days_until_expiry()
        assert 0.0 <= result <= 2.0

    def test_today_midnight_is_near_zero(self):
        """Expiry at midnight of today is either 0 or a small fraction remaining."""
        today = datetime.now().strftime("%Y-%m-%d")
        result = _make_monitor(expiry_date=today)._days_until_expiry()
        assert result >= 0.0
        assert result < 1.0


# ---------------------------------------------------------------------------
# CreditUsage.to_dict
# ---------------------------------------------------------------------------

class TestCreditUsageToDict:

    def _usage(self, **kw):
        defaults = dict(
            timestamp=datetime(2026, 4, 29, 12, 0, 0),
            credits_used=5.0,
            credits_remaining=20.0,
            session_cost=0.5,
            daily_burn=2.0,
            days_remaining=10.0,
        )
        defaults.update(kw)
        return CreditUsage(**defaults)

    def test_all_expected_keys_present(self):
        d = self._usage().to_dict()
        for key in ("timestamp", "credits_used", "credits_remaining",
                    "session_cost", "daily_burn", "days_remaining"):
            assert key in d

    def test_timestamp_is_isoformat_string(self):
        ts = datetime(2026, 4, 29, 12, 0, 0)
        assert self._usage(timestamp=ts).to_dict()["timestamp"] == ts.isoformat()

    def test_numeric_fields_match(self):
        d = self._usage(credits_remaining=15.5, daily_burn=3.25).to_dict()
        assert d["credits_remaining"] == 15.5
        assert d["daily_burn"] == 3.25


# ---------------------------------------------------------------------------
# BudgetAlert dataclass
# ---------------------------------------------------------------------------

class TestBudgetAlert:

    def test_default_sent_is_false(self):
        alert = BudgetAlert("warning", 2.0, "Test")
        assert alert.sent is False

    def test_fields_set_correctly(self):
        alert = BudgetAlert("critical", 1.0, "Critical!", sent=True)
        assert alert.level == "critical"
        assert alert.threshold_days == 1.0
        assert alert.message == "Critical!"
        assert alert.sent is True


# ---------------------------------------------------------------------------
# get_usage_summary — status emoji threshold logic (async, mocked)
# ---------------------------------------------------------------------------

class TestGetUsageSummaryStatus:
    """Verify the CRITICAL/WARNING/CAUTION/HEALTHY status branches."""

    def _run(self, m, days_remaining):
        with patch.object(m, "get_current_usage",
                          new=AsyncMock(return_value=_make_usage(days_remaining))):
            return asyncio.run(m.get_usage_summary())

    def test_critical_at_half_day(self):
        result = self._run(_make_monitor(), 0.5)
        assert "CRITICAL" in result["status"]

    def test_warning_at_one_and_half_days(self):
        result = self._run(_make_monitor(), 1.5)
        assert "WARNING" in result["status"]

    def test_caution_at_three_days(self):
        result = self._run(_make_monitor(), 3.0)
        assert "CAUTION" in result["status"]

    def test_healthy_at_ten_days(self):
        result = self._run(_make_monitor(), 10.0)
        assert "HEALTHY" in result["status"]

    def test_error_when_no_usage_data(self):
        m = _make_monitor()
        with patch.object(m, "get_current_usage", new=AsyncMock(return_value=None)):
            result = asyncio.run(m.get_usage_summary())
        assert "error" in result

    def test_utilization_pct_calculation(self):
        m = _make_monitor(budget=25.0)
        usage = _make_usage(10.0, credits_used=5.0, credits_remaining=20.0)
        with patch.object(m, "get_current_usage", new=AsyncMock(return_value=usage)):
            result = asyncio.run(m.get_usage_summary())
        # 5.0 / 25.0 * 100 = 20%
        assert abs(result["utilization_pct"] - 20.0) < 0.01

    def test_expiry_date_surfaced_in_result(self):
        m = _make_monitor(expiry_date="2099-12-31")
        with patch.object(m, "get_current_usage",
                          new=AsyncMock(return_value=_make_usage(30.0))):
            result = asyncio.run(m.get_usage_summary())
        assert result["expiry_date"] == "2099-12-31"

    def test_budget_limit_surfaced_in_result(self):
        m = _make_monitor(budget=50.0)
        with patch.object(m, "get_current_usage",
                          new=AsyncMock(return_value=_make_usage(10.0))):
            result = asyncio.run(m.get_usage_summary())
        assert result["budget_limit"] == 50.0


# ---------------------------------------------------------------------------
# health_check — async, mocked get_current_usage
# ---------------------------------------------------------------------------

class TestHealthCheck:
    """Verify health_check returns correct status strings."""

    def _run(self, m):
        return asyncio.run(m.health_check())

    def test_no_api_key_returns_not_configured(self):
        m = _make_monitor()
        m.api_key = None
        assert self._run(m) == "not_configured"

    def test_api_key_with_usage_returns_ok(self):
        m = _make_monitor()
        m.api_key = "sk-test-key"
        with patch.object(m, "get_current_usage",
                          new=AsyncMock(return_value=_make_usage(10.0))):
            assert self._run(m) == "ok"

    def test_api_key_with_no_usage_returns_error(self):
        m = _make_monitor()
        m.api_key = "sk-test-key"
        with patch.object(m, "get_current_usage", new=AsyncMock(return_value=None)):
            assert self._run(m) == "error"

    def test_exception_during_get_usage_returns_error(self):
        m = _make_monitor()
        m.api_key = "sk-test-key"
        with patch.object(m, "get_current_usage",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert self._run(m) == "error"


# ---------------------------------------------------------------------------
# record_usage — async, file I/O fully mocked
# ---------------------------------------------------------------------------

class TestRecordUsage:
    """Verify record_usage orchestrates load/compute/save/alert correctly."""

    def _run(self, m, session_cost, description=""):
        return asyncio.run(m.record_usage(session_cost, description))

    def test_happy_path_returns_true(self):
        m = _make_monitor()
        with patch.object(m, "_load_usage_history", new=AsyncMock(return_value=[])), \
             patch.object(m, "get_current_usage",
                          new=AsyncMock(return_value=_make_usage(10.0))), \
             patch.object(m, "_save_usage_history", new=AsyncMock(return_value=True)), \
             patch.object(m, "_check_budget_alerts", new=AsyncMock()):
            assert self._run(m, 1.0, "test session") is True

    def test_get_current_usage_none_returns_false(self):
        m = _make_monitor()
        with patch.object(m, "_load_usage_history", new=AsyncMock(return_value=[])), \
             patch.object(m, "get_current_usage", new=AsyncMock(return_value=None)):
            assert self._run(m, 1.0) is False

    def test_save_failure_returns_false(self):
        m = _make_monitor()
        with patch.object(m, "_load_usage_history", new=AsyncMock(return_value=[])), \
             patch.object(m, "get_current_usage",
                          new=AsyncMock(return_value=_make_usage(10.0))), \
             patch.object(m, "_save_usage_history", new=AsyncMock(return_value=False)), \
             patch.object(m, "_check_budget_alerts", new=AsyncMock()):
            assert self._run(m, 1.0) is False

    def test_credits_remaining_and_used_updated_correctly(self):
        m = _make_monitor()
        usage = _make_usage(10.0, credits_used=5.0, credits_remaining=20.0)
        save_mock = AsyncMock(return_value=True)
        with patch.object(m, "_load_usage_history", new=AsyncMock(return_value=[])), \
             patch.object(m, "get_current_usage", new=AsyncMock(return_value=usage)), \
             patch.object(m, "_save_usage_history", new=save_mock), \
             patch.object(m, "_check_budget_alerts", new=AsyncMock()):
            self._run(m, 2.0)
        saved = save_mock.call_args[0][0]
        assert abs(saved[-1]["credits_remaining"] - 18.0) < 0.01  # 20 - 2
        assert abs(saved[-1]["credits_used"] - 7.0) < 0.01        # 5 + 2

    def test_description_stored_in_saved_entry(self):
        m = _make_monitor()
        save_mock = AsyncMock(return_value=True)
        with patch.object(m, "_load_usage_history", new=AsyncMock(return_value=[])), \
             patch.object(m, "get_current_usage",
                          new=AsyncMock(return_value=_make_usage(10.0))), \
             patch.object(m, "_save_usage_history", new=save_mock), \
             patch.object(m, "_check_budget_alerts", new=AsyncMock()):
            self._run(m, 1.0, "my description")
        assert save_mock.call_args[0][0][-1]["description"] == "my description"

    def test_old_entries_pruned_beyond_30_days(self):
        """Entries older than 30 days must be filtered out before save."""
        m = _make_monitor()
        old_entry = _entry(datetime.now() - timedelta(days=31), 25.0)
        old_entry["description"] = "old"
        save_mock = AsyncMock(return_value=True)
        with patch.object(m, "_load_usage_history",
                          new=AsyncMock(return_value=[old_entry])), \
             patch.object(m, "get_current_usage",
                          new=AsyncMock(return_value=_make_usage(10.0))), \
             patch.object(m, "_save_usage_history", new=save_mock), \
             patch.object(m, "_check_budget_alerts", new=AsyncMock()):
            self._run(m, 1.0)
        saved = save_mock.call_args[0][0]
        # Old entry pruned; only the newly appended entry remains
        assert len(saved) == 1
        assert saved[0].get("description", "") != "old"

    def test_recent_entries_kept(self):
        """Entries within 30 days must survive the cutoff filter."""
        m = _make_monitor()
        recent = _entry(datetime.now() - timedelta(days=10), 22.0)
        save_mock = AsyncMock(return_value=True)
        with patch.object(m, "_load_usage_history",
                          new=AsyncMock(return_value=[recent])), \
             patch.object(m, "get_current_usage",
                          new=AsyncMock(return_value=_make_usage(10.0))), \
             patch.object(m, "_save_usage_history", new=save_mock), \
             patch.object(m, "_check_budget_alerts", new=AsyncMock()):
            self._run(m, 1.0)
        saved = save_mock.call_args[0][0]
        assert len(saved) == 2  # recent entry + new entry

    def test_alerts_checked_when_save_succeeds(self):
        m = _make_monitor()
        alerts_mock = AsyncMock()
        with patch.object(m, "_load_usage_history", new=AsyncMock(return_value=[])), \
             patch.object(m, "get_current_usage",
                          new=AsyncMock(return_value=_make_usage(10.0))), \
             patch.object(m, "_save_usage_history", new=AsyncMock(return_value=True)), \
             patch.object(m, "_check_budget_alerts", new=alerts_mock):
            self._run(m, 1.0)
        alerts_mock.assert_called_once()

    def test_alerts_not_checked_when_save_fails(self):
        m = _make_monitor()
        alerts_mock = AsyncMock()
        with patch.object(m, "_load_usage_history", new=AsyncMock(return_value=[])), \
             patch.object(m, "get_current_usage",
                          new=AsyncMock(return_value=_make_usage(10.0))), \
             patch.object(m, "_save_usage_history", new=AsyncMock(return_value=False)), \
             patch.object(m, "_check_budget_alerts", new=alerts_mock):
            self._run(m, 1.0)
        alerts_mock.assert_not_called()

    def test_exception_in_load_returns_false(self):
        m = _make_monitor()
        with patch.object(m, "_load_usage_history",
                          new=AsyncMock(side_effect=RuntimeError("disk full"))):
            assert self._run(m, 1.0) is False
