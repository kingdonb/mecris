"""
Unit tests for fetch_groq_usage.py

Uses GroqUsageScraper.__new__ to bypass __init__ (avoids NEON_DB_URL/credential
checks). Pattern consistent with test_groq_odometer_tracker.py.

psycopg2 and playwright are not installed in CI; they are injected into
sys.modules as MagicMocks at module level (same pattern as test_scheduler_jobs.py).

Coverage:
  - get_cached_usage()  — DB hit, DB miss, no neon_url, DB exception
  - cache_usage_data()  — DB upsert, no neon_url, DB exception, expiry window
  - scrape_usage_data() — missing creds, playwright success (data found),
                          playwright success (no data / regex fallback),
                          playwright exception
  - get_usage_data()    — cache hit path, cache miss + scrape success,
                          cache miss + scrape failure, cache age field
  - _get_cache_age_minutes() — valid ISO string, Z-suffix, bad input, future ts
  - fetch_groq_usage()  — module-level convenience function
"""

import json
import sys
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Bootstrap unavailable optional deps before fetch_groq_usage is imported
# ---------------------------------------------------------------------------

_mock_psycopg2 = MagicMock()
_mock_psycopg2_extras = MagicMock()
_mock_playwright = MagicMock()
_mock_playwright_sync_api = MagicMock()

sys.modules.setdefault("psycopg2", _mock_psycopg2)
sys.modules.setdefault("psycopg2.extras", _mock_psycopg2_extras)
sys.modules.setdefault("playwright", _mock_playwright)
sys.modules.setdefault("playwright.sync_api", _mock_playwright_sync_api)

import fetch_groq_usage  # noqa: E402 — must be after sys.modules bootstrap
from fetch_groq_usage import GroqUsageScraper, fetch_groq_usage as _fetch_groq_usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scraper(neon_url="postgresql://fake/db", email="u@x.com", password="pw"):
    """Build a GroqUsageScraper bypassing __init__."""
    s = GroqUsageScraper.__new__(GroqUsageScraper)
    s.neon_url = neon_url
    s.email = email
    s.password = password
    s.cache_minutes = 15
    return s


def _make_mock_conn(mock_cursor):
    """Wrap a mock cursor in a minimal psycopg2 connection context manager."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn


# ---------------------------------------------------------------------------
# get_cached_usage
# ---------------------------------------------------------------------------

class TestGetCachedUsage:
    def test_returns_none_when_no_neon_url(self):
        s = _make_scraper(neon_url=None)
        assert s.get_cached_usage() is None

    def test_returns_parsed_json_on_cache_hit(self):
        s = _make_scraper()
        payload = {"success": True, "data": {"amount_0": "$1.23"}}

        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {"cache_data": json.dumps(payload)}
        mock_conn = _make_mock_conn(mock_cur)

        with patch.object(sys.modules["psycopg2"], "connect", return_value=mock_conn):
            result = s.get_cached_usage()

        assert result == payload
        mock_cur.execute.assert_called_once()
        sql = mock_cur.execute.call_args[0][0]
        assert "SELECT cache_data" in sql

    def test_returns_none_on_cache_miss(self):
        s = _make_scraper()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn = _make_mock_conn(mock_cur)

        with patch.object(sys.modules["psycopg2"], "connect", return_value=mock_conn):
            result = s.get_cached_usage()

        assert result is None

    def test_returns_none_on_db_exception(self):
        s = _make_scraper()
        with patch.object(sys.modules["psycopg2"], "connect", side_effect=Exception("conn refused")):
            result = s.get_cached_usage()
        assert result is None

    def test_queries_correct_provider_and_key(self):
        s = _make_scraper()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn = _make_mock_conn(mock_cur)

        with patch.object(sys.modules["psycopg2"], "connect", return_value=mock_conn):
            s.get_cached_usage()

        args = mock_cur.execute.call_args[0][1]
        assert args[0] == "groq"
        assert args[1] == "usage_data"


# ---------------------------------------------------------------------------
# cache_usage_data
# ---------------------------------------------------------------------------

class TestCacheUsageData:
    def test_no_op_when_no_neon_url(self):
        s = _make_scraper(neon_url=None)
        # Should return without raising or touching psycopg2
        s.cache_usage_data({"success": True})

    def test_executes_upsert_on_success(self):
        s = _make_scraper()
        data = {"success": True, "data": {"amount_0": "$2.50"}}

        mock_cur = MagicMock()
        mock_conn = _make_mock_conn(mock_cur)

        with patch.object(sys.modules["psycopg2"], "connect", return_value=mock_conn):
            s.cache_usage_data(data)

        mock_cur.execute.assert_called_once()
        sql = mock_cur.execute.call_args[0][0]
        assert "INSERT INTO provider_cache" in sql
        assert "ON CONFLICT" in sql

        args = mock_cur.execute.call_args[0][1]
        assert args[0] == "groq"
        assert args[1] == "usage_data"
        assert json.loads(args[2]) == data

    def test_expires_at_is_cache_minutes_in_future(self):
        s = _make_scraper()
        s.cache_minutes = 30

        mock_cur = MagicMock()
        mock_conn = _make_mock_conn(mock_cur)

        before = datetime.now()
        with patch.object(sys.modules["psycopg2"], "connect", return_value=mock_conn):
            s.cache_usage_data({"x": 1})
        after = datetime.now()

        args = mock_cur.execute.call_args[0][1]
        expires_at = args[4]
        assert expires_at >= before + timedelta(minutes=30)
        assert expires_at <= after + timedelta(minutes=30)

    def test_silences_db_exception(self):
        s = _make_scraper()
        with patch.object(sys.modules["psycopg2"], "connect", side_effect=Exception("write failed")):
            # Should not raise
            s.cache_usage_data({"x": 1})


# ---------------------------------------------------------------------------
# scrape_usage_data
# ---------------------------------------------------------------------------

def _mock_playwright_ctx(mock_page):
    """Build a mock sync_playwright context manager with the given page."""
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser.new_context.return_value = mock_context

    mock_pw = MagicMock()
    mock_pw.__enter__ = MagicMock(return_value=mock_pw)
    mock_pw.__exit__ = MagicMock(return_value=False)
    mock_pw.chromium.launch.return_value = mock_browser
    return mock_pw


class TestScrapeUsageData:
    def test_returns_error_dict_when_no_credentials(self):
        s = _make_scraper(email=None, password=None)
        result = s.scrape_usage_data()
        assert result["success"] is False
        assert "Missing credentials" in result["error"]
        assert result["source"] == "scraper"

    def test_returns_error_when_only_email_missing(self):
        s = _make_scraper(email=None)
        result = s.scrape_usage_data()
        assert result["success"] is False

    def test_returns_error_when_only_password_missing(self):
        s = _make_scraper(password=None)
        result = s.scrape_usage_data()
        assert result["success"] is False

    def test_returns_success_when_playwright_finds_data(self):
        s = _make_scraper()

        mock_page = MagicMock()
        mock_element = MagicMock()
        mock_element.inner_text.return_value = "$3.45"
        mock_page.query_selector_all.return_value = [mock_element]
        mock_page.query_selector.return_value = None
        mock_page.inner_text.return_value = ""

        mock_pw = _mock_playwright_ctx(mock_page)
        sys.modules["playwright.sync_api"].sync_playwright.return_value = mock_pw

        result = s.scrape_usage_data()

        assert result["success"] is True
        assert "data" in result
        assert result["source"] == "scraper"
        assert "scraped_at" in result

    def test_returns_failure_when_no_data_found(self):
        s = _make_scraper()

        mock_page = MagicMock()
        mock_page.query_selector_all.return_value = []
        mock_page.query_selector.return_value = None
        mock_page.inner_text.return_value = "No dollar amounts here"

        mock_pw = _mock_playwright_ctx(mock_page)
        sys.modules["playwright.sync_api"].sync_playwright.return_value = mock_pw

        result = s.scrape_usage_data()

        assert result["success"] is False
        assert result["source"] == "scraper"

    def test_returns_failure_on_playwright_exception(self):
        s = _make_scraper()
        sys.modules["playwright.sync_api"].sync_playwright.side_effect = Exception("browser crashed")
        try:
            result = s.scrape_usage_data()
        finally:
            sys.modules["playwright.sync_api"].sync_playwright.side_effect = None

        assert result["success"] is False
        assert "browser crashed" in result["error"]
        assert result["source"] == "scraper"

    def test_fallback_regex_finds_dollar_amounts(self):
        """When no selector matches, body text regex is used."""
        s = _make_scraper()

        mock_page = MagicMock()
        mock_page.query_selector_all.return_value = []
        mock_page.query_selector.return_value = None
        mock_page.inner_text.return_value = "You spent $4.56 this month, also $7.89"

        mock_pw = _mock_playwright_ctx(mock_page)
        sys.modules["playwright.sync_api"].sync_playwright.return_value = mock_pw

        result = s.scrape_usage_data()

        assert result["success"] is True
        assert "$4.56" in result["data"]["detected_amounts"]
        assert "$7.89" in result["data"]["detected_amounts"]


# ---------------------------------------------------------------------------
# get_usage_data
# ---------------------------------------------------------------------------

class TestGetUsageData:
    def test_returns_cached_data_when_cache_hit(self):
        s = _make_scraper()
        cached = {
            "success": True,
            "data": {"amount_0": "$1.00"},
            "scraped_at": datetime.now().isoformat(),
        }

        with patch.object(s, "get_cached_usage", return_value=cached):
            result = s.get_usage_data()

        assert result["cached"] is True
        assert "cache_age_minutes" in result
        assert result["success"] is True

    def test_scrapes_when_no_cache(self):
        s = _make_scraper()
        scraped = {
            "success": True,
            "data": {"amount_0": "$2.00"},
            "scraped_at": datetime.now().isoformat(),
            "source": "scraper",
        }

        with patch.object(s, "get_cached_usage", return_value=None), \
             patch.object(s, "scrape_usage_data", return_value=scraped) as mock_scrape, \
             patch.object(s, "cache_usage_data") as mock_cache:
            result = s.get_usage_data()

        mock_scrape.assert_called_once()
        mock_cache.assert_called_once_with(scraped)
        assert result["cached"] is False
        assert result["success"] is True

    def test_does_not_cache_on_scrape_failure(self):
        s = _make_scraper()
        scraped = {"success": False, "error": "no data", "source": "scraper"}

        with patch.object(s, "get_cached_usage", return_value=None), \
             patch.object(s, "scrape_usage_data", return_value=scraped), \
             patch.object(s, "cache_usage_data") as mock_cache:
            result = s.get_usage_data()

        mock_cache.assert_not_called()
        assert result["cached"] is False
        assert result["success"] is False

    def test_cache_age_appended_to_cached_result(self):
        s = _make_scraper()
        scraped_at = (datetime.now() - timedelta(minutes=5)).isoformat()
        cached = {"success": True, "scraped_at": scraped_at}

        with patch.object(s, "get_cached_usage", return_value=cached):
            result = s.get_usage_data()

        assert result["cache_age_minutes"] >= 5


# ---------------------------------------------------------------------------
# _get_cache_age_minutes
# ---------------------------------------------------------------------------

class TestGetCacheAgeMinutes:
    def test_returns_zero_on_none_input(self):
        s = _make_scraper()
        assert s._get_cache_age_minutes(None) == 0

    def test_returns_zero_on_non_date_string(self):
        s = _make_scraper()
        assert s._get_cache_age_minutes("not-a-date") == 0

    def test_calculates_minutes_from_iso_string(self):
        s = _make_scraper()
        past = (datetime.now() - timedelta(minutes=10)).isoformat()
        age = s._get_cache_age_minutes(past)
        assert 9 <= age <= 11

    def test_handles_z_suffix_iso_string(self):
        s = _make_scraper()
        past = (datetime.now() - timedelta(minutes=3)).isoformat() + "Z"
        age = s._get_cache_age_minutes(past)
        assert 2 <= age <= 4

    def test_returns_int_for_future_timestamp(self):
        """Timestamp in the future — result is a negative int truncated to 0 by int()."""
        s = _make_scraper()
        future = (datetime.now() + timedelta(minutes=10)).isoformat()
        age = s._get_cache_age_minutes(future)
        assert isinstance(age, int)


# ---------------------------------------------------------------------------
# fetch_groq_usage (module-level function)
# ---------------------------------------------------------------------------

class TestFetchGroqUsage:
    def test_calls_scraper_get_usage_data(self):
        fake_result = {"success": True, "cached": False, "source": "scraper"}

        with patch("fetch_groq_usage.GroqUsageScraper") as MockScraper:
            instance = MockScraper.return_value
            instance.get_usage_data.return_value = fake_result
            result = _fetch_groq_usage()

        MockScraper.assert_called_once()
        instance.get_usage_data.assert_called_once()
        assert result == fake_result

    def test_returns_dict(self):
        with patch("fetch_groq_usage.GroqUsageScraper") as MockScraper:
            instance = MockScraper.return_value
            instance.get_usage_data.return_value = {"success": False}
            result = _fetch_groq_usage()

        assert isinstance(result, dict)
