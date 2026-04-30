"""
Tests for claude_api_budget_scraper.py

Coverage groups:
  CreditBalance             — dataclass fields and to_dict()
  ClaudeConsoleScraper init — URLs, env-var credentials, cache settings
  _load_cached_balance      — cache miss, fresh hit, stale, bad JSON
  _save_cached_balance      — write success, write error (no exception)
  _scaffold_scraper         — returns CreditBalance with mock values
  _playwright_implementation— always returns None (stub)
  get_credit_balance        — cache hit / miss dispatch
  set_manual_balance        — UsageTracker delegation, CreditBalance build
  Convenience functions     — get_claude_balance, update_balance_manually
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from claude_api_budget_scraper import (
    ClaudeConsoleScraper,
    CreditBalance,
    get_claude_balance,
    update_balance_manually,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_balance(**kwargs) -> CreditBalance:
    defaults = dict(
        total_credits=100.0,
        used_credits=30.0,
        remaining_credits=70.0,
        billing_period_start="2026-01-01",
        billing_period_end="2026-01-31",
        last_updated=datetime(2026, 1, 15, 12, 0, 0),
    )
    defaults.update(kwargs)
    return CreditBalance(**defaults)


def _fresh_cache_data() -> dict:
    return {
        "total_credits": 50.0,
        "used_credits": 10.0,
        "remaining_credits": 40.0,
        "billing_period_start": "2026-04-01",
        "billing_period_end": "2026-04-30",
        "last_updated": datetime.now().isoformat(),
    }


def _stale_cache_data() -> dict:
    stale_ts = (datetime.now() - timedelta(hours=2)).isoformat()
    data = _fresh_cache_data()
    data["last_updated"] = stale_ts
    return data


# ---------------------------------------------------------------------------
# Group 1: CreditBalance
# ---------------------------------------------------------------------------

class TestCreditBalance:
    def test_to_dict_returns_required_keys(self):
        b = _make_balance()
        d = b.to_dict()
        expected_keys = {
            "total_credits", "used_credits", "remaining_credits",
            "billing_period_start", "billing_period_end", "last_updated",
        }
        assert expected_keys == set(d.keys())

    def test_to_dict_last_updated_is_isoformat_string(self):
        b = _make_balance()
        d = b.to_dict()
        # Verify it's a string parseable by fromisoformat
        parsed = datetime.fromisoformat(d["last_updated"])
        assert isinstance(parsed, datetime)

    def test_to_dict_numeric_values_match(self):
        b = _make_balance(total_credits=200.0, used_credits=50.0, remaining_credits=150.0)
        d = b.to_dict()
        assert d["total_credits"] == 200.0
        assert d["used_credits"] == 50.0
        assert d["remaining_credits"] == 150.0

    def test_fields_directly_accessible(self):
        b = _make_balance(billing_period_start="2026-03-01", billing_period_end="2026-03-31")
        assert b.billing_period_start == "2026-03-01"
        assert b.billing_period_end == "2026-03-31"


# ---------------------------------------------------------------------------
# Group 2: ClaudeConsoleScraper.__init__
# ---------------------------------------------------------------------------

class TestClaudeConsoleScraper_Init:
    def test_default_urls(self):
        s = ClaudeConsoleScraper()
        assert "console.anthropic.com/settings/billing" in s.console_url
        assert "console.anthropic.com/login" in s.login_url

    def test_reads_credentials_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_CONSOLE_EMAIL", "test@example.com")
        monkeypatch.setenv("ANTHROPIC_CONSOLE_PASSWORD", "s3cr3t")
        s = ClaudeConsoleScraper()
        assert s.email == "test@example.com"
        assert s.password == "s3cr3t"

    def test_default_cache_settings(self):
        s = ClaudeConsoleScraper()
        assert s.cache_duration_hours == 1
        assert s.cache_file.endswith(".json")
        assert s.session_file.endswith(".json")


# ---------------------------------------------------------------------------
# Group 3: _load_cached_balance
# ---------------------------------------------------------------------------

class TestLoadCachedBalance:
    def test_no_cache_file_returns_none(self):
        s = ClaudeConsoleScraper()
        with patch("os.path.exists", return_value=False):
            result = asyncio.run(s._load_cached_balance())
        assert result is None

    def test_fresh_cache_returns_credit_balance(self):
        s = ClaudeConsoleScraper()
        data = _fresh_cache_data()
        m = mock_open(read_data=json.dumps(data))
        with patch("os.path.exists", return_value=True), patch("builtins.open", m):
            result = asyncio.run(s._load_cached_balance())
        assert isinstance(result, CreditBalance)
        assert result.total_credits == data["total_credits"]
        assert result.remaining_credits == data["remaining_credits"]

    def test_stale_cache_returns_none(self):
        s = ClaudeConsoleScraper()
        data = _stale_cache_data()
        m = mock_open(read_data=json.dumps(data))
        with patch("os.path.exists", return_value=True), patch("builtins.open", m):
            result = asyncio.run(s._load_cached_balance())
        assert result is None

    def test_bad_json_returns_none(self):
        s = ClaudeConsoleScraper()
        m = mock_open(read_data="not valid json{{")
        with patch("os.path.exists", return_value=True), patch("builtins.open", m):
            result = asyncio.run(s._load_cached_balance())
        assert result is None


# ---------------------------------------------------------------------------
# Group 4: _save_cached_balance
# ---------------------------------------------------------------------------

class TestSaveCachedBalance:
    def test_writes_json_to_file(self):
        s = ClaudeConsoleScraper()
        b = _make_balance()
        m = mock_open()
        with patch("builtins.open", m):
            asyncio.run(s._save_cached_balance(b))
        m.assert_called_once_with(s.cache_file, "w")
        handle = m()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        parsed = json.loads(written)
        assert parsed["total_credits"] == 100.0

    def test_write_error_does_not_raise(self):
        s = ClaudeConsoleScraper()
        b = _make_balance()
        with patch("builtins.open", side_effect=IOError("disk full")):
            # Must not raise
            asyncio.run(s._save_cached_balance(b))


# ---------------------------------------------------------------------------
# Group 5: _scaffold_scraper_implementation
# ---------------------------------------------------------------------------

class TestScaffoldScraper:
    def test_returns_credit_balance_not_none(self):
        s = ClaudeConsoleScraper()
        result = asyncio.run(s._scaffold_scraper_implementation())
        assert isinstance(result, CreditBalance)

    def test_mock_values_match_scaffold(self):
        s = ClaudeConsoleScraper()
        result = asyncio.run(s._scaffold_scraper_implementation())
        assert result.total_credits == 25.0
        assert result.used_credits == 6.79
        assert result.remaining_credits == 18.21


# ---------------------------------------------------------------------------
# Group 6: _playwright_implementation
# ---------------------------------------------------------------------------

class TestPlaywrightImplementation:
    def test_returns_none(self):
        s = ClaudeConsoleScraper()
        result = asyncio.run(s._playwright_implementation())
        assert result is None


# ---------------------------------------------------------------------------
# Group 7: get_credit_balance
# ---------------------------------------------------------------------------

class TestGetCreditBalance:
    def test_cache_hit_returns_cached_balance(self):
        s = ClaudeConsoleScraper()
        cached = _make_balance()
        s._load_cached_balance = AsyncMock(return_value=cached)
        s._scaffold_scraper_implementation = AsyncMock()
        result = asyncio.run(s.get_credit_balance())
        assert result is cached
        s._scaffold_scraper_implementation.assert_not_called()

    def test_no_cache_calls_scaffold(self):
        s = ClaudeConsoleScraper()
        scaffold_result = _make_balance(total_credits=25.0)
        s._load_cached_balance = AsyncMock(return_value=None)
        s._scaffold_scraper_implementation = AsyncMock(return_value=scaffold_result)
        result = asyncio.run(s.get_credit_balance())
        assert result is scaffold_result
        s._scaffold_scraper_implementation.assert_called_once()

    def test_returns_credit_balance_type(self):
        s = ClaudeConsoleScraper()
        s._load_cached_balance = AsyncMock(return_value=None)
        s._scaffold_scraper_implementation = AsyncMock(return_value=_make_balance())
        result = asyncio.run(s.get_credit_balance())
        assert isinstance(result, CreditBalance)


# ---------------------------------------------------------------------------
# Group 8: set_manual_balance
# ---------------------------------------------------------------------------

_MOCK_BUDGET_INFO = {
    "total": 25.0,
    "remaining": 15.50,
    "period_start": "2026-04-01",
    "period_end": "2026-04-30",
    "last_updated": "2026-04-15T10:00:00",
}


class TestSetManualBalance:
    def test_calls_update_budget_with_remaining_only(self):
        s = ClaudeConsoleScraper()
        with patch("usage_tracker.UsageTracker.update_budget", return_value=_MOCK_BUDGET_INFO):
            result = s.set_manual_balance(15.50)
        assert isinstance(result, CreditBalance)

    def test_calls_update_budget_with_all_args(self):
        s = ClaudeConsoleScraper()
        with patch("usage_tracker.UsageTracker.update_budget", return_value=_MOCK_BUDGET_INFO) as mock_ub:
            s.set_manual_balance(15.50, total_credits=25.0, period_end="2026-04-30")
        mock_ub.assert_called_once_with(15.50, 25.0, "2026-04-30")

    def test_credit_balance_fields_from_budget_info(self):
        s = ClaudeConsoleScraper()
        with patch("usage_tracker.UsageTracker.update_budget", return_value=_MOCK_BUDGET_INFO):
            result = s.set_manual_balance(15.50)
        assert result.total_credits == 25.0
        assert result.remaining_credits == 15.50
        assert result.used_credits == pytest.approx(25.0 - 15.50)
        assert result.billing_period_start == "2026-04-01"
        assert result.billing_period_end == "2026-04-30"


# ---------------------------------------------------------------------------
# Group 9: Convenience functions
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    def test_get_claude_balance_returns_credit_balance(self):
        mock_balance = _make_balance()
        with patch.object(ClaudeConsoleScraper, "get_credit_balance", new=AsyncMock(return_value=mock_balance)):
            result = asyncio.run(get_claude_balance())
        assert result is mock_balance

    def test_update_balance_manually_delegates(self):
        mock_balance = _make_balance()
        with patch.object(ClaudeConsoleScraper, "set_manual_balance", return_value=mock_balance) as mock_sbm:
            result = update_balance_manually(15.50, total=25.0, period_end="2026-04-30")
        mock_sbm.assert_called_once_with(15.50, 25.0, "2026-04-30")
        assert result is mock_balance
