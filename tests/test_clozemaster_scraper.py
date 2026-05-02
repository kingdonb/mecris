"""Unit tests for ClozemasterScraper class methods.

Covers: _load_credentials, login, get_review_forecast, _enrich_with_api_forecast.
The sync_clozemaster_to_beeminder integration path is covered by test_clozemaster_idempotency.py.
"""
import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Bootstrap psycopg2 mock before any import that might pull it in
# ---------------------------------------------------------------------------
import sys as _sys

_mock_psycopg2 = MagicMock()
_sys.modules.setdefault("psycopg2", _mock_psycopg2)

# ---------------------------------------------------------------------------
# Helpers to build a minimal ClozemasterScraper without running __init__
# ---------------------------------------------------------------------------

def _fresh_scraper():
    """Return a ClozemasterScraper instance with __init__ bypassed."""
    from scripts.clozemaster_scraper import ClozemasterScraper
    s = ClozemasterScraper.__new__(ClozemasterScraper)
    s.user_id = None
    s.email = None
    s.password = None
    s.base_url = "https://www.clozemaster.com"
    s.csrf_token = ""
    s.cookies = {}
    s.headers = {"User-Agent": "test-agent"}
    # Mock the httpx async client
    s.client = MagicMock()
    s.client.get = AsyncMock()
    s.client.post = AsyncMock()
    s.client.aclose = AsyncMock()
    # Mock service dependencies
    s.encryption = MagicMock()
    s.tracker = MagicMock()
    s.tracker.resolve_user_id.return_value = "test-user-123"
    return s


def _make_mock_response(status_code=200, text="", url="https://test.com", json_data=None):
    """Build a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.url = url
    resp.cookies = {}
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


# ---------------------------------------------------------------------------
# _load_credentials tests
# ---------------------------------------------------------------------------

class TestLoadCredentials:

    def test_no_neon_url_uses_env_vars(self, monkeypatch):
        """Falls back to CLOZEMASTER_EMAIL/PASSWORD when NEON_DB_URL is absent."""
        s = _fresh_scraper()
        monkeypatch.delenv("NEON_DB_URL", raising=False)
        monkeypatch.setenv("CLOZEMASTER_EMAIL", "user@example.com")
        monkeypatch.setenv("CLOZEMASTER_PASSWORD", "secret")

        asyncio.run(s._load_credentials())

        assert s.email == "user@example.com"
        assert s.password == "secret"

    def test_no_neon_url_no_env_vars_raises(self, monkeypatch):
        """Raises RuntimeError when NEON_DB_URL and legacy env vars are both absent."""
        s = _fresh_scraper()
        monkeypatch.delenv("NEON_DB_URL", raising=False)
        monkeypatch.delenv("CLOZEMASTER_EMAIL", raising=False)
        monkeypatch.delenv("CLOZEMASTER_PASSWORD", raising=False)

        with pytest.raises(RuntimeError, match="NEON_DB_URL not set"):
            asyncio.run(s._load_credentials())

    def test_neon_db_decrypts_credentials(self, monkeypatch):
        """Loads and decrypts credentials from Neon when DB row is present."""
        s = _fresh_scraper()
        monkeypatch.setenv("NEON_DB_URL", "postgresql://test")

        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = ("enc_email", "enc_pass")

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur

        s.encryption.decrypt.side_effect = lambda x: x.replace("enc_", "decrypted_")

        with patch.object(sys.modules["psycopg2"], "connect", return_value=mock_conn):
            asyncio.run(s._load_credentials())

        assert s.email == "decrypted_email"
        assert s.password == "decrypted_pass"

    def test_neon_db_row_none_falls_back_to_env(self, monkeypatch):
        """Falls back to env vars when DB row is None."""
        s = _fresh_scraper()
        monkeypatch.setenv("NEON_DB_URL", "postgresql://test")
        monkeypatch.setenv("CLOZEMASTER_EMAIL", "env@example.com")
        monkeypatch.setenv("CLOZEMASTER_PASSWORD", "env_pass")

        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur

        with patch.object(sys.modules["psycopg2"], "connect", return_value=mock_conn):
            asyncio.run(s._load_credentials())

        assert s.email == "env@example.com"
        assert s.password == "env_pass"

    def test_neon_db_row_none_no_env_raises(self, monkeypatch):
        """Raises RuntimeError when DB row is None and env vars missing."""
        s = _fresh_scraper()
        monkeypatch.setenv("NEON_DB_URL", "postgresql://test")
        monkeypatch.delenv("CLOZEMASTER_EMAIL", raising=False)
        monkeypatch.delenv("CLOZEMASTER_PASSWORD", raising=False)

        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur

        with patch.object(sys.modules["psycopg2"], "connect", return_value=mock_conn):
            with pytest.raises(RuntimeError, match="No Clozemaster credentials"):
                asyncio.run(s._load_credentials())

    def test_neon_db_connect_exception_propagates(self, monkeypatch):
        """Exceptions from psycopg2.connect propagate as RuntimeError."""
        s = _fresh_scraper()
        monkeypatch.setenv("NEON_DB_URL", "postgresql://test")

        with patch.object(sys.modules["psycopg2"], "connect", side_effect=Exception("connection refused")):
            with pytest.raises(Exception, match="connection refused"):
                asyncio.run(s._load_credentials())


# ---------------------------------------------------------------------------
# login tests
# ---------------------------------------------------------------------------

def _make_login_html(csrf_token="tok123", inputs=None):
    """Generate minimal HTML with login form fields."""
    input_fields = inputs or [
        '<input name="authenticity_token" value="tok123">',
        '<input name="user[email]" value="">',
        '<input name="user[password]" value="">',
    ]
    return (
        "<html><body><form>"
        + "".join(input_fields)
        + "</form></body></html>"
    )


class TestLogin:

    def test_login_success_dashboard_in_url(self):
        """Returns True when redirect URL contains 'dashboard'."""
        s = _fresh_scraper()
        s.email = "u@example.com"
        s.password = "pass"

        login_page = _make_login_html()
        dashboard_resp = _make_mock_response(200, "Welcome", url="https://www.clozemaster.com/dashboard")
        dashboard_resp.cookies = {"_session": "abc"}

        s.client.get = AsyncMock(return_value=_make_mock_response(200, login_page))
        s.client.post = AsyncMock(return_value=dashboard_resp)

        result = asyncio.run(s.login())

        assert result is True

    def test_login_success_dashboard_in_text(self):
        """Returns True when response text contains 'Dashboard'."""
        s = _fresh_scraper()
        s.email = "u@example.com"
        s.password = "pass"

        login_page = _make_login_html()
        success_resp = _make_mock_response(200, "Dashboard content", url="https://www.clozemaster.com/")
        success_resp.cookies = {}

        s.client.get = AsyncMock(return_value=_make_mock_response(200, login_page))
        s.client.post = AsyncMock(return_value=success_resp)

        result = asyncio.run(s.login())

        assert result is True

    def test_login_failure_returns_false(self):
        """Returns False when redirect does not indicate success."""
        s = _fresh_scraper()
        s.email = "u@example.com"
        s.password = "wrong"

        login_page = _make_login_html()
        fail_resp = _make_mock_response(200, "Invalid credentials", url="https://www.clozemaster.com/login")
        fail_resp.cookies = {}

        s.client.get = AsyncMock(return_value=_make_mock_response(200, login_page))
        s.client.post = AsyncMock(return_value=fail_resp)

        result = asyncio.run(s.login())

        assert result is False

    def test_login_exception_returns_false(self):
        """Returns False when httpx raises an exception."""
        s = _fresh_scraper()
        s.email = "u@example.com"
        s.password = "pass"

        s.client.get = AsyncMock(side_effect=Exception("network error"))

        result = asyncio.run(s.login())

        assert result is False

    def test_login_uses_user_login_field_when_present(self):
        """Uses user[login] field name when present in form inputs."""
        s = _fresh_scraper()
        s.email = "u@example.com"
        s.password = "pass"

        # Form has user[login] instead of user[email]
        login_page = _make_login_html(inputs=[
            '<input name="authenticity_token" value="tok999">',
            '<input name="user[login]" value="">',
        ])
        success_resp = _make_mock_response(200, "Dashboard", url="https://clozemaster.com/dashboard")
        success_resp.cookies = {}

        s.client.get = AsyncMock(return_value=_make_mock_response(200, login_page))
        s.client.post = AsyncMock(return_value=success_resp)

        asyncio.run(s.login())

        post_call_data = s.client.post.call_args[1]["data"]
        assert "user[login]" in post_call_data

    def test_login_extracts_csrf_token_from_page(self):
        """CSRF token is extracted from the login page and sent in the form."""
        s = _fresh_scraper()
        s.email = "u@example.com"
        s.password = "pass"

        login_page = _make_login_html(csrf_token="csrf_abc")
        success_resp = _make_mock_response(200, "Dashboard", url="https://clozemaster.com/dashboard")
        success_resp.cookies = {}

        s.client.get = AsyncMock(return_value=_make_mock_response(200, login_page))
        s.client.post = AsyncMock(return_value=success_resp)

        asyncio.run(s.login())

        post_data = s.client.post.call_args[1]["data"]
        assert post_data["authenticity_token"] == "tok123"

    def test_login_loads_credentials_when_missing(self):
        """Calls _load_credentials if email/password are not set."""
        s = _fresh_scraper()
        # email/password intentionally left None

        load_called = []

        async def fake_load():
            s.email = "loaded@example.com"
            s.password = "loaded_pass"
            load_called.append(True)

        s._load_credentials = fake_load

        login_page = _make_login_html()
        success_resp = _make_mock_response(200, "Dashboard", url="https://clozemaster.com/dashboard")
        success_resp.cookies = {}

        s.client.get = AsyncMock(return_value=_make_mock_response(200, login_page))
        s.client.post = AsyncMock(return_value=success_resp)

        asyncio.run(s.login())

        assert load_called, "_load_credentials was not called"


# ---------------------------------------------------------------------------
# get_review_forecast tests
# ---------------------------------------------------------------------------

def _make_dashboard_html(lang_slug="ara-eng", num_ready=42, lp_id=99, csrf_meta="csrf_meta_token"):
    """Generate minimal HTML mimicking Clozemaster DashboardV5 React props."""
    import json, html as html_mod
    props = {
        "languagePairings": [
            {
                "slug": lang_slug,
                "numReadyForReview": num_ready,
                "score": 1000,
                "numPointsToday": 50,
                "id": lp_id,
            }
        ]
    }
    props_str = html_mod.escape(json.dumps(props))
    return f"""<html><head>
<meta name="csrf-token" content="{csrf_meta}">
</head><body>
<div data-react-class="DashboardV5" data-react-props="{props_str}"></div>
</body></html>"""


class TestGetReviewForecast:

    def test_non_200_returns_empty(self):
        """Returns default empty dict when dashboard returns non-200."""
        s = _fresh_scraper()
        s.client.get = AsyncMock(return_value=_make_mock_response(403, "Forbidden"))

        result = asyncio.run(s.get_review_forecast("ara-eng"))

        assert result["today"] == 0
        assert result["tomorrow"] == 0
        assert result["next_7_days"] == 0

    def test_no_dashboard_div_returns_empty(self):
        """Returns empty dict when DashboardV5 div is absent."""
        s = _fresh_scraper()
        s.client.get = AsyncMock(return_value=_make_mock_response(200, "<html><body></body></html>"))

        result = asyncio.run(s.get_review_forecast("ara-eng"))

        assert result["today"] == 0

    def test_found_pairing_returns_count(self):
        """Returns today count from matching language pairing."""
        s = _fresh_scraper()
        html = _make_dashboard_html(lang_slug="ara-eng", num_ready=2600, lp_id=None)
        # No lp_id → no enrich call
        import json, html as html_mod
        props = {"languagePairings": [{"slug": "ara-eng", "numReadyForReview": 2600, "score": 5000, "numPointsToday": 10}]}
        html = f'<html><head><meta name="csrf-token" content="x"></head><body><div data-react-class="DashboardV5" data-react-props="{html_mod.escape(json.dumps(props))}"></div></body></html>'

        s.client.get = AsyncMock(return_value=_make_mock_response(200, html))

        result = asyncio.run(s.get_review_forecast("ara-eng"))

        assert result["today"] == 2600
        assert result["points"] == 5000

    def test_unmatched_lang_slug_returns_zero(self):
        """Returns zeros when slug doesn't match any pairing."""
        s = _fresh_scraper()
        html = _make_dashboard_html(lang_slug="fra-eng", num_ready=99, lp_id=None)

        s.client.get = AsyncMock(return_value=_make_mock_response(200, html))

        result = asyncio.run(s.get_review_forecast("ara-eng"))

        assert result["today"] == 0

    def test_exception_returns_empty(self):
        """Returns default empty dict when get raises an exception."""
        s = _fresh_scraper()
        s.client.get = AsyncMock(side_effect=Exception("timeout"))

        result = asyncio.run(s.get_review_forecast("ara-eng"))

        assert result["today"] == 0

    def test_csrf_token_extracted_from_meta(self):
        """CSRF token is updated from dashboard meta tag."""
        s = _fresh_scraper()
        import json, html as html_mod
        props = {"languagePairings": []}
        html = f'<html><head><meta name="csrf-token" content="new_token_xyz"></head><body><div data-react-class="DashboardV5" data-react-props="{html_mod.escape(json.dumps(props))}"></div></body></html>'

        s.client.get = AsyncMock(return_value=_make_mock_response(200, html))

        asyncio.run(s.get_review_forecast("ara-eng"))

        assert s.csrf_token == "new_token_xyz"

    def test_enrich_called_when_lp_id_present(self):
        """Calls _enrich_with_api_forecast when pairing has an id."""
        s = _fresh_scraper()

        enrich_calls = []

        async def fake_enrich(lp_id, forecast, lang_slug):
            enrich_calls.append(lp_id)

        s._enrich_with_api_forecast = fake_enrich

        html = _make_dashboard_html(lang_slug="ara-eng", num_ready=10, lp_id=77)
        s.client.get = AsyncMock(return_value=_make_mock_response(200, html))

        asyncio.run(s.get_review_forecast("ara-eng"))

        assert enrich_calls == [77]


# ---------------------------------------------------------------------------
# _enrich_with_api_forecast tests
# ---------------------------------------------------------------------------

def _make_more_stats_json(review_forecast=None, ttm_played=None, stats_per_day=None):
    """Build a fake more-stats API response."""
    from datetime import date
    today = date.today().isoformat()
    return {
        "reviewForecast": review_forecast or [{"count": 5}, {"count": 3}, {"count": 2}],
        "ttmNumPlayedByDate": ttm_played or [{"date": today, "numPlayed": 42}],
        "statsPerDay": stats_per_day or [],
    }


class TestEnrichWithApiForecast:

    def test_enriches_tomorrow_and_7day(self):
        """Parses reviewForecast and sets tomorrow/next_7_days."""
        s = _fresh_scraper()
        forecast = {"today": 10, "tomorrow": 0, "next_7_days": 0}
        data = _make_more_stats_json(
            review_forecast=[{"count": 5}, {"count": 3}, {"count": 2}, {"count": 1}, {"count": 1}, {"count": 1}, {"count": 0}]
        )
        s.client.get = AsyncMock(return_value=_make_mock_response(200, json_data=data))

        asyncio.run(s._enrich_with_api_forecast(99, forecast, "ara-eng"))

        assert forecast["tomorrow"] == 5
        assert forecast["next_7_days"] == 13  # sum of first 7

    def test_non_200_leaves_forecast_unchanged(self):
        """Leaves forecast dict unchanged when API returns non-200."""
        s = _fresh_scraper()
        forecast = {"today": 10, "tomorrow": 0, "next_7_days": 0}
        s.client.get = AsyncMock(return_value=_make_mock_response(404))

        asyncio.run(s._enrich_with_api_forecast(99, forecast, "ara-eng"))

        assert forecast["tomorrow"] == 0
        assert forecast["next_7_days"] == 0

    def test_ttm_played_sets_cards_today(self):
        """Sets forecast['cards_today'] from ttmNumPlayedByDate for today."""
        from datetime import date
        s = _fresh_scraper()
        forecast = {"today": 10, "tomorrow": 0, "next_7_days": 0}
        today = date.today().isoformat()
        data = _make_more_stats_json(ttm_played=[{"date": today, "numPlayed": 37}])
        s.client.get = AsyncMock(return_value=_make_mock_response(200, json_data=data))

        asyncio.run(s._enrich_with_api_forecast(99, forecast, "ara-eng"))

        assert forecast.get("cards_today") == 37

    def test_empty_review_forecast_leaves_tomorrow_zero(self):
        """Does not crash on empty reviewForecast list."""
        s = _fresh_scraper()
        forecast = {"today": 10, "tomorrow": 0, "next_7_days": 0}
        data = {"reviewForecast": [], "ttmNumPlayedByDate": [], "statsPerDay": []}
        s.client.get = AsyncMock(return_value=_make_mock_response(200, json_data=data))

        asyncio.run(s._enrich_with_api_forecast(99, forecast, "ara-eng"))

        assert forecast["tomorrow"] == 0

    def test_exception_is_swallowed(self):
        """Exceptions during enrichment do not propagate (logged as warning)."""
        s = _fresh_scraper()
        forecast = {"today": 10, "tomorrow": 0, "next_7_days": 0}
        s.client.get = AsyncMock(side_effect=Exception("API down"))

        # Should not raise
        asyncio.run(s._enrich_with_api_forecast(99, forecast, "ara-eng"))

    def test_integer_forecast_items_summed(self):
        """Handles bare integer forecast items (not dicts)."""
        s = _fresh_scraper()
        forecast = {"today": 10, "tomorrow": 0, "next_7_days": 0}
        data = {"reviewForecast": [4, 3, 2, 1, 1, 1, 1], "ttmNumPlayedByDate": [], "statsPerDay": []}
        s.client.get = AsyncMock(return_value=_make_mock_response(200, json_data=data))

        asyncio.run(s._enrich_with_api_forecast(99, forecast, "ara-eng"))

        assert forecast["tomorrow"] == 4
        assert forecast["next_7_days"] == 13

    def test_correct_api_url_called(self):
        """Calls the correct more-stats API URL for the LP id."""
        s = _fresh_scraper()
        forecast = {"today": 0, "tomorrow": 0, "next_7_days": 0}
        data = {"reviewForecast": [], "ttmNumPlayedByDate": [], "statsPerDay": []}
        s.client.get = AsyncMock(return_value=_make_mock_response(200, json_data=data))

        asyncio.run(s._enrich_with_api_forecast(42, forecast, "ara-eng"))

        call_url = s.client.get.call_args[0][0]
        assert "/api/v1/lp/42/more-stats" in call_url


# ---------------------------------------------------------------------------
# close test
# ---------------------------------------------------------------------------

def test_close_calls_aclose():
    """close() awaits client.aclose()."""
    s = _fresh_scraper()
    asyncio.run(s.close())
    s.client.aclose.assert_awaited_once()
