"""
Unit tests for scripts/anthropic_cost_tracker.py

Covers:
- AnthropicCostTracker.__init__ (key validation)
- _rate_limited_request (unsupported method, timeout, rate-limit wait, header injection)
- get_usage (param building for 1h/today vs 1d/historical, cache hit/miss)
- get_cost (param building, cache hit/miss)
- get_budget_summary (aggregation from usage + cost data)
"""

import sys
import time
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call

# ── bootstrap: requests is available; import the module under test ──────────
from scripts.anthropic_cost_tracker import AnthropicCostTracker


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fresh_tracker(key="test-admin-key"):
    """Return an AnthropicCostTracker with a real key (no env dependency)."""
    return AnthropicCostTracker(admin_api_key=key)


def _utcnow():
    return datetime.now(timezone.utc)


def _make_usage_response(n_buckets=2, results_per_bucket=3):
    """Build a fake usage API response."""
    return {
        "data": [
            {"results": [{"uncached_input_tokens": 100, "output_tokens": 50}] * results_per_bucket}
            for _ in range(n_buckets)
        ],
        "has_more": False,
    }


def _make_cost_response(n_buckets=1, results_per_bucket=2):
    """Build a fake cost API response."""
    return {
        "data": [
            {"results": [{"amount": 0.05}] * results_per_bucket}
            for _ in range(n_buckets)
        ],
        "has_more": True,
    }


# ─────────────────────────────────────────────────────────────────────────────
# __init__ tests
# ─────────────────────────────────────────────────────────────────────────────

class TestInit:
    def test_key_from_argument(self):
        t = AnthropicCostTracker(admin_api_key="my-key")
        assert t.admin_api_key == "my-key"

    def test_key_from_env(self):
        with patch.dict("os.environ", {"ANTHROPIC_ADMIN_KEY": "env-key"}, clear=False):
            t = AnthropicCostTracker()
        assert t.admin_api_key == "env-key"

    def test_raises_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="No Anthropic Admin API key"):
                AnthropicCostTracker()

    def test_explicit_key_overrides_env(self):
        with patch.dict("os.environ", {"ANTHROPIC_ADMIN_KEY": "env-key"}, clear=False):
            t = AnthropicCostTracker(admin_api_key="explicit-key")
        assert t.admin_api_key == "explicit-key"

    def test_initial_cache_empty(self):
        t = _fresh_tracker()
        assert t.usage_cache == {}
        assert t.cost_cache == {}

    def test_min_interval_default(self):
        t = _fresh_tracker()
        assert t._min_interval == 10

    def test_last_api_call_starts_at_zero(self):
        t = _fresh_tracker()
        assert t._last_api_call == 0


# ─────────────────────────────────────────────────────────────────────────────
# _rate_limited_request tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRateLimitedRequest:
    def test_unsupported_method_raises(self):
        t = _fresh_tracker()
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            t._rate_limited_request("https://example.com", method="DELETE")

    def test_get_injects_auth_headers(self):
        t = _fresh_tracker(key="secret-key")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        with patch("requests.get", return_value=mock_resp) as mock_get:
            result = t._rate_limited_request("https://api.anthropic.com/v1/test")
        args, kwargs = mock_get.call_args
        assert kwargs["headers"]["x-api-key"] == "secret-key"
        assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
        assert result == {"ok": True}

    def test_post_method_called(self):
        t = _fresh_tracker()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            t._rate_limited_request("https://api.anthropic.com/v1/test", method="POST")
        mock_post.assert_called_once()

    def test_raises_for_status_called(self):
        t = _fresh_tracker()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        with patch("requests.get", return_value=mock_resp):
            t._rate_limited_request("https://api.anthropic.com/v1/test")
        mock_resp.raise_for_status.assert_called_once()

    def test_timeout_propagates(self):
        import requests as req
        t = _fresh_tracker()
        with patch("requests.get", side_effect=req.exceptions.Timeout("timed out")):
            with pytest.raises(req.exceptions.Timeout):
                t._rate_limited_request("https://api.anthropic.com/v1/test")

    def test_rate_limit_wait_when_recent_call(self):
        t = _fresh_tracker()
        # Simulate a very recent call (only 2s ago, min_interval=10)
        t._last_api_call = time.time() - 2
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        with patch("requests.get", return_value=mock_resp):
            with patch("time.sleep") as mock_sleep:
                t._rate_limited_request("https://api.anthropic.com/v1/test")
        # Should have slept approximately 8s (10 - 2)
        mock_sleep.assert_called_once()
        sleep_arg = mock_sleep.call_args[0][0]
        assert 7 < sleep_arg < 9

    def test_no_sleep_when_interval_elapsed(self):
        t = _fresh_tracker()
        # Last call was 30s ago — well past min_interval
        t._last_api_call = time.time() - 30
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        with patch("requests.get", return_value=mock_resp):
            with patch("time.sleep") as mock_sleep:
                t._rate_limited_request("https://api.anthropic.com/v1/test")
        mock_sleep.assert_not_called()

    def test_extra_headers_merged(self):
        t = _fresh_tracker(key="k")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        with patch("requests.get", return_value=mock_resp) as mock_get:
            t._rate_limited_request(
                "https://api.anthropic.com/v1/test",
                headers={"X-Custom": "val"},
            )
        headers = mock_get.call_args[1]["headers"]
        assert headers["X-Custom"] == "val"
        assert headers["x-api-key"] == "k"


# ─────────────────────────────────────────────────────────────────────────────
# get_usage tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGetUsage:
    def test_historical_includes_ending_at(self):
        """Past date range → params must include ending_at."""
        t = _fresh_tracker()
        yesterday = _utcnow() - timedelta(days=2)
        day_before = yesterday - timedelta(days=1)
        fake = _make_usage_response()
        with patch.object(t, "_rate_limited_request", return_value=fake) as mock_req:
            t.get_usage(start_time=day_before, end_time=yesterday, bucket_width="1d")
        params = mock_req.call_args[1]["params"]
        assert "ending_at" in params
        assert "starting_at" in params

    def test_today_1h_omits_ending_at(self):
        """Today's data with 1h bucket → ending_at must be omitted."""
        t = _fresh_tracker()
        now = _utcnow()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        fake = _make_usage_response()
        with patch.object(t, "_rate_limited_request", return_value=fake) as mock_req:
            t.get_usage(start_time=start, end_time=now, bucket_width="1h")
        params = mock_req.call_args[1]["params"]
        assert "ending_at" not in params
        assert params["bucket_width"] == "1h"

    def test_default_start_end_times(self):
        """No start/end provided → defaults to last 24 hours."""
        t = _fresh_tracker()
        fake = _make_usage_response()
        with patch.object(t, "_rate_limited_request", return_value=fake):
            result = t.get_usage()
        assert result == fake

    def test_cache_hit_skips_request(self):
        """Second identical call with fresh cache → no API call."""
        t = _fresh_tracker()
        fake = _make_usage_response()
        with patch.object(t, "_rate_limited_request", return_value=fake) as mock_req:
            r1 = t.get_usage()
            r2 = t.get_usage()
        assert mock_req.call_count == 1
        assert r1 == r2

    def test_cache_miss_after_expiry(self):
        """Stale cache (>60s old) → new API call made."""
        t = _fresh_tracker()
        fake = _make_usage_response()
        with patch.object(t, "_rate_limited_request", return_value=fake) as mock_req:
            t.get_usage()
            # Age the cache entry
            for key in t.usage_cache:
                data, _ = t.usage_cache[key]
                t.usage_cache[key] = (data, time.time() - 61)
            t.get_usage()
        assert mock_req.call_count == 2

    def test_iso_format_uses_z_suffix(self):
        """starting_at in params must end with 'Z'."""
        t = _fresh_tracker()
        past = _utcnow() - timedelta(days=3)
        fake = _make_usage_response()
        with patch.object(t, "_rate_limited_request", return_value=fake) as mock_req:
            t.get_usage(start_time=past, end_time=_utcnow() - timedelta(days=2))
        params = mock_req.call_args[1]["params"]
        assert params["starting_at"].endswith("Z")

    def test_bucket_width_default_1d(self):
        """Default bucket_width is '1d'."""
        t = _fresh_tracker()
        past = _utcnow() - timedelta(days=2)
        fake = _make_usage_response()
        with patch.object(t, "_rate_limited_request", return_value=fake) as mock_req:
            t.get_usage(start_time=past - timedelta(days=1), end_time=past)
        params = mock_req.call_args[1]["params"]
        assert params["bucket_width"] == "1d"


# ─────────────────────────────────────────────────────────────────────────────
# get_cost tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGetCost:
    def test_params_include_both_timestamps(self):
        t = _fresh_tracker()
        end = _utcnow() - timedelta(days=1)
        start = end - timedelta(days=1)
        fake = _make_cost_response()
        with patch.object(t, "_rate_limited_request", return_value=fake) as mock_req:
            t.get_cost(start_time=start, end_time=end)
        params = mock_req.call_args[1]["params"]
        assert "starting_at" in params
        assert "ending_at" in params
        assert params["bucket_width"] == "1d"

    def test_default_times_make_request(self):
        t = _fresh_tracker()
        fake = _make_cost_response()
        with patch.object(t, "_rate_limited_request", return_value=fake):
            result = t.get_cost()
        assert result == fake

    def test_cache_hit(self):
        t = _fresh_tracker()
        fake = _make_cost_response()
        with patch.object(t, "_rate_limited_request", return_value=fake) as mock_req:
            t.get_cost()
            t.get_cost()
        assert mock_req.call_count == 1

    def test_cache_miss_after_expiry(self):
        t = _fresh_tracker()
        fake = _make_cost_response()
        with patch.object(t, "_rate_limited_request", return_value=fake) as mock_req:
            t.get_cost()
            for key in t.cost_cache:
                data, _ = t.cost_cache[key]
                t.cost_cache[key] = (data, time.time() - 61)
            t.get_cost()
        assert mock_req.call_count == 2

    def test_iso_z_suffix_on_both_params(self):
        t = _fresh_tracker()
        end = _utcnow() - timedelta(days=2)
        start = end - timedelta(days=1)
        fake = _make_cost_response()
        with patch.object(t, "_rate_limited_request", return_value=fake) as mock_req:
            t.get_cost(start_time=start, end_time=end)
        params = mock_req.call_args[1]["params"]
        assert params["starting_at"].endswith("Z")
        assert params["ending_at"].endswith("Z")


# ─────────────────────────────────────────────────────────────────────────────
# get_budget_summary tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGetBudgetSummary:
    def _patch_both(self, t, usage_resp, cost_resp):
        patcher_u = patch.object(t, "get_usage", return_value=usage_resp)
        patcher_c = patch.object(t, "get_cost", return_value=cost_resp)
        return patcher_u, patcher_c

    def test_returns_expected_keys(self):
        t = _fresh_tracker()
        u = _make_usage_response(2, 3)
        c = _make_cost_response(1, 2)
        with patch.object(t, "get_usage", return_value=u), \
             patch.object(t, "get_cost", return_value=c):
            summary = t.get_budget_summary()
        assert set(summary.keys()) == {
            "usage_buckets", "cost_buckets",
            "total_message_records", "total_cost_records",
            "has_more_usage", "has_more_cost",
            "timestamp",
        }

    def test_bucket_counts(self):
        t = _fresh_tracker()
        u = _make_usage_response(n_buckets=3, results_per_bucket=4)
        c = _make_cost_response(n_buckets=2, results_per_bucket=1)
        with patch.object(t, "get_usage", return_value=u), \
             patch.object(t, "get_cost", return_value=c):
            summary = t.get_budget_summary()
        assert summary["usage_buckets"] == 3
        assert summary["cost_buckets"] == 2

    def test_total_record_counts(self):
        t = _fresh_tracker()
        u = _make_usage_response(n_buckets=2, results_per_bucket=3)  # 6 total
        c = _make_cost_response(n_buckets=1, results_per_bucket=5)  # 5 total
        with patch.object(t, "get_usage", return_value=u), \
             patch.object(t, "get_cost", return_value=c):
            summary = t.get_budget_summary()
        assert summary["total_message_records"] == 6
        assert summary["total_cost_records"] == 5

    def test_has_more_flags(self):
        t = _fresh_tracker()
        u = {"data": [], "has_more": True}
        c = {"data": [], "has_more": False}
        with patch.object(t, "get_usage", return_value=u), \
             patch.object(t, "get_cost", return_value=c):
            summary = t.get_budget_summary()
        assert summary["has_more_usage"] is True
        assert summary["has_more_cost"] is False

    def test_empty_data_returns_zeros(self):
        t = _fresh_tracker()
        u = {"data": [], "has_more": False}
        c = {"data": [], "has_more": False}
        with patch.object(t, "get_usage", return_value=u), \
             patch.object(t, "get_cost", return_value=c):
            summary = t.get_budget_summary()
        assert summary["total_message_records"] == 0
        assert summary["total_cost_records"] == 0
        assert summary["usage_buckets"] == 0
        assert summary["cost_buckets"] == 0

    def test_timestamp_is_iso_string(self):
        t = _fresh_tracker()
        u = {"data": [], "has_more": False}
        c = {"data": [], "has_more": False}
        with patch.object(t, "get_usage", return_value=u), \
             patch.object(t, "get_cost", return_value=c):
            summary = t.get_budget_summary()
        # Must be parseable as ISO datetime
        dt = datetime.fromisoformat(summary["timestamp"])
        assert dt is not None

    def test_buckets_with_no_results_key(self):
        """Bucket missing 'results' key → treated as zero records (safe default)."""
        t = _fresh_tracker()
        u = {"data": [{"no_results_key": True}, {"results": [1, 2]}], "has_more": False}
        c = {"data": [], "has_more": False}
        with patch.object(t, "get_usage", return_value=u), \
             patch.object(t, "get_cost", return_value=c):
            summary = t.get_budget_summary()
        assert summary["total_message_records"] == 2
