"""
Tests for scripts/openrouter_usage_tracker.py — OpenRouterTracker class.

Validates org-wide usage aggregation, dollar sync, and envelope integration.
"""

import os
import pytest
from datetime import datetime, timezone, date, timedelta
from unittest.mock import patch, MagicMock, call

# Load the module
import importlib.util
spec = importlib.util.spec_from_file_location(
    "openrouter_usage_tracker",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "openrouter_usage_tracker.py")
)
tracker_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tracker_module)

OpenRouterTracker = tracker_module.OpenRouterTracker


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_env():
    """Provide mock environment variables."""
    env = {
        "NEON_DB_URL": "postgresql://test:test@localhost/test",
        "OPENROUTER_API_KEY": "sk-or-test-123",
        "OPENROUTER_MANAGEMENT_KEY": "sk-or-mgmt-456",
        "DEFAULT_USER_ID": "test-user-uuid",
    }
    with patch.dict(os.environ, env, clear=False):
        yield env


@pytest.fixture
def tracker(mock_env):
    """Create tracker with mocked DB init."""
    with patch.object(OpenRouterTracker, "_init_db"):
        t = OpenRouterTracker()
    return t


# ---------------------------------------------------------------------------
# _fetch_keys_usage
# ---------------------------------------------------------------------------

class TestFetchKeysUsage:
    def test_returns_empty_list_when_no_mgmt_key(self, tracker):
        tracker.management_key = None
        result = tracker._fetch_keys_usage()
        assert result == []

    def test_returns_key_data_on_success(self, tracker):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {
                    "label": "Key 1",
                    "hash": "abc123",
                    "usage_daily": 150,
                    "usage_weekly": 800,
                    "usage_monthly": 3000,
                    "limit": 1000,
                    "limit_remaining": 850,
                    "limit_reset": "daily",
                    "usage": 5000,
                    "byok_usage_daily": 0,
                },
                {
                    "label": "Key 2",
                    "hash": "def456",
                    "usage_daily": 250,
                    "usage_weekly": 1200,
                    "usage_monthly": 5000,
                    "limit": 0,
                    "limit_remaining": 0,
                    "limit_reset": None,
                    "usage": 10000,
                    "byok_usage_daily": 0,
                },
            ]
        }
        mock_resp.raise_for_status.return_value = None

        with patch("scripts.openrouter_usage_tracker.requests.get", return_value=mock_resp) as mock_get:
            result = tracker._fetch_keys_usage()

        assert len(result) == 2
        assert result[0]["label"] == "Key 1"
        assert result[0]["usage_daily"] == 150
        assert result[1]["usage_daily"] == 250
        mock_get.assert_called_once()

    def test_returns_empty_on_exception(self, tracker):
        with patch("scripts.openrouter_usage_tracker.requests.get", side_effect=Exception("network")):
            result = tracker._fetch_keys_usage()
        assert result == []


# ---------------------------------------------------------------------------
# _fetch_credits
# ---------------------------------------------------------------------------

class TestFetchCredits:
    def test_returns_defaults_when_no_api_key(self, tracker):
        tracker.api_key = None
        result = tracker._fetch_credits()
        assert result == {"total_credits": 10.0, "total_usage": 0.0, "remaining": 10.0}

    def test_returns_parsed_usage_on_success(self, tracker):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"total_credits": 10.0, "total_usage": 2.34}}
        mock_resp.raise_for_status.return_value = None

        with patch("scripts.openrouter_usage_tracker.requests.get", return_value=mock_resp) as mock_get:
            result = tracker._fetch_credits()

        assert result == {"total_credits": 10.0, "total_usage": 2.34, "remaining": 7.66}
        mock_get.assert_called_once()

    def test_returns_defaults_on_exception(self, tracker):
        with patch("scripts.openrouter_usage_tracker.requests.get", side_effect=Exception("network")):
            result = tracker._fetch_credits()
        assert result == {"total_credits": 10.0, "total_usage": 0.0, "remaining": 10.0}


# ---------------------------------------------------------------------------
# sync_org_usage
# ---------------------------------------------------------------------------

class TestSyncOrgUsage:
    def test_aggregates_daily_requests_from_keys(self, tracker):
        # Mock _fetch_keys_usage
        with patch.object(tracker, "_fetch_keys_usage", return_value=[
            {"usage_daily": 171, "usage_weekly": 765, "usage_monthly": 3150, "label": "Key 1", "hash": "abc123"},
            {"usage_daily": 50, "usage_weekly": 200, "usage_monthly": 1000, "label": "Key 2", "hash": "def456"},
        ]), patch.object(tracker, "_fetch_credits", return_value={"total_credits": 10.0, "total_usage": 1.23, "remaining": 8.77}):
            
            # Mock DB
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conn.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            with patch("scripts.openrouter_usage_tracker.psycopg2.connect", return_value=mock_conn):
                result = tracker.sync_org_usage()

        assert result["synced"] is True
        assert result["daily_requests"] == 221  # 171 + 50
        assert result["weekly_requests"] == 965  # 765 + 200
        assert result["monthly_requests"] == 4150  # 3150 + 1000
        assert result["dollar_credits"] == 10.0
        assert result["dollar_usage"] == 1.23
        assert result["dollar_remaining"] == 8.77

    def test_handles_missing_dollar_usage(self, tracker):
        with patch.object(tracker, "_fetch_keys_usage", return_value=[
            {"usage_daily": 100, "usage_weekly": 500, "usage_monthly": 2000, "label": "Key 1", "hash": "abc"},
        ]), patch.object(tracker, "_fetch_credits", return_value={"total_credits": 10.0, "total_usage": 0.0, "remaining": 10.0}):
            
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conn.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            
            with patch("scripts.openrouter_usage_tracker.psycopg2.connect", return_value=mock_conn):
                result = tracker.sync_org_usage()

        assert result["synced"] is True
        assert result["dollar_usage"] == 0.0


# ---------------------------------------------------------------------------
# get_daily_status
# ---------------------------------------------------------------------------

class TestGetDailyStatus:
    def test_returns_zero_when_no_db(self, tracker):
        tracker.neon_url = None
        result = tracker.get_daily_status()
        assert "error" in result

    def test_returns_aggregated_status(self, tracker):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # Mock daily requests row
        mock_cur.fetchone.side_effect = [
            {"request_count": 420},  # daily requests
            {"total_credits": 10.0, "total_usage": 3.14, "remaining_credits": 6.86, "recorded_at": datetime.now(timezone.utc)},
        ]
        
        with patch("scripts.openrouter_usage_tracker.psycopg2.connect", return_value=mock_conn):
            result = tracker.get_daily_status()

        assert result["requests"]["daily_used"] == 420
        assert result["requests"]["daily_limit"] == 1000
        assert result["requests"]["daily_remaining"] == 580
        assert result["requests"]["envelope_status"] == "allow"
        assert result["dollars"]["total_credits"] == 10.0
        assert result["dollars"]["total_usage"] == 3.14
        assert result["dollars"]["remaining"] == 6.86

    def test_envelope_status_deny_when_exhausted(self, tracker):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        mock_cur.fetchone.side_effect = [
            {"request_count": 1000},
            {"total_credits": 10.0, "total_usage": 0.0, "remaining_credits": 10.0, "recorded_at": datetime.now(timezone.utc)},
        ]
        
        with patch("scripts.openrouter_usage_tracker.psycopg2.connect", return_value=mock_conn):
            result = tracker.get_daily_status()

        assert result["requests"]["envelope_status"] == "deny"
        assert result["requests"]["daily_remaining"] == 0


# ---------------------------------------------------------------------------
# get_narrator_summary
# ---------------------------------------------------------------------------

class TestGetNarratorSummary:
    def test_returns_tracking_summary(self, tracker):
        with patch.object(tracker, "get_daily_status", return_value={
            "requests": {"daily_used": 171, "daily_limit": 1000, "daily_remaining": 829, "envelope_status": "allow"},
            "dollars": {"total_credits": 10.0, "total_usage": 1.23, "remaining": 8.77, "last_synced": "2025-01-15T10:00:00Z"}
        }):
            summary = tracker.get_narrator_summary()

        assert summary["openrouter_tracking"]["daily_requests_used"] == 171
        assert summary["openrouter_tracking"]["daily_requests_remaining"] == 829
        assert summary["openrouter_tracking"]["dollar_usage"] == 1.23
        assert summary["openrouter_tracking"]["needs_action"] is False

    def test_sets_needs_action_when_requests_low(self, tracker):
        with patch.object(tracker, "get_daily_status", return_value={
            "requests": {"daily_used": 950, "daily_limit": 1000, "daily_remaining": 50, "envelope_status": "allow"},
            "dollars": {"total_credits": 10.0, "total_usage": 1.0, "remaining": 9.0, "last_synced": "2025-01-15T10:00:00Z"}
        }):
            summary = tracker.get_narrator_summary()

        assert summary["openrouter_tracking"]["needs_action"] is True
        assert "urgent_reminder" in summary["openrouter_tracking"]
        assert "50 requests left" in summary["openrouter_tracking"]["urgent_reminder"]

    def test_sets_needs_action_when_dollars_low(self, tracker):
        with patch.object(tracker, "get_daily_status", return_value={
            "requests": {"daily_used": 100, "daily_limit": 1000, "daily_remaining": 900, "envelope_status": "allow"},
            "dollars": {"total_credits": 10.0, "total_usage": 9.50, "remaining": 0.50, "last_synced": "2025-01-15T10:00:00Z"}
        }):
            summary = tracker.get_narrator_summary()

        assert summary["openrouter_tracking"]["needs_action"] is True
        assert "urgent_reminder" in summary["openrouter_tracking"]
        assert "$0.50 remaining" in summary["openrouter_tracking"]["urgent_reminder"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])