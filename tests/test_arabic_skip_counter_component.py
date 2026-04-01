"""
Tests for mecris-go-spin/arabic-skip-counter/app.py (Phase 1.6: HTTP trigger)

Validates the helper functions (_count_reminders, _parse_query_params,
_json_response, _error_json) directly against the same scenarios as
test_arabic_skip_count.py.  Tests run against the Python source directly
(not the compiled WASM) — componentize-py wraps this same logic.

The IncomingHandler class requires the WASM runtime (spin_sdk) and is NOT
tested here.  HTTP end-to-end validation requires `spin test` in the
deployment environment.
"""

import sys
import os

import pytest
from unittest.mock import MagicMock, patch

# Add the component directory to the path so we can import app.py
_COMPONENT_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "mecris-go-spin",
    "arabic-skip-counter",
)
sys.path.insert(0, os.path.abspath(_COMPONENT_DIR))

import app


# ---------------------------------------------------------------------------
# _count_reminders — Neon HTTP query logic (unchanged from Phase 1.5b)
# ---------------------------------------------------------------------------


class TestCountReminders:
    """_count_reminders() queries Neon and returns a skip count."""

    def test_returns_int_on_success(self):
        """Returns an int on a successful Neon response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": [{"count": "5"}]}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.post", return_value=mock_response):
            result = app._count_reminders(
                "postgres://user:pw@host.neon.tech/db", "yebyen", 24
            )
        assert isinstance(result, int)
        assert result == 5

    def test_returns_zero_on_http_error(self):
        """Returns 0 (never raises) on HTTP failure — fail-safe."""
        with patch("httpx.post", side_effect=Exception("network error")):
            result = app._count_reminders(
                "postgres://user:pw@host.neon.tech/db", "yebyen", 24
            )
        assert result == 0

    def test_returns_zero_on_empty_rows(self):
        """Returns 0 when Neon returns an empty rows list."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": []}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.post", return_value=mock_response):
            result = app._count_reminders(
                "postgres://user:pw@host.neon.tech/db", "yebyen", 24
            )
        assert result == 0

    def test_hours_parameter_passed_through(self):
        """The hours parameter changes the cutoff window passed to Neon."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": [{"count": "2"}]}
        mock_response.raise_for_status.return_value = None

        captured_params = []

        def capture_post(url, **kwargs):
            captured_params.append(kwargs.get("json", {}).get("params", []))
            return mock_response

        with patch("httpx.post", side_effect=capture_post):
            app._count_reminders(
                "postgres://user:pw@host.neon.tech/db", "yebyen", 48
            )

        assert len(captured_params) == 1
        params = captured_params[0]
        # params: [type1, type2, user_id, cutoff_iso]
        assert params[2] == "yebyen"
        assert isinstance(params[3], str)
        assert "T" in params[3]  # ISO datetime has T separator

    def test_neon_url_parsed_correctly(self):
        """HTTP endpoint is derived from the postgres:// URL correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": [{"count": "0"}]}
        mock_response.raise_for_status.return_value = None

        captured_urls = []

        def capture_post(url, **kwargs):
            captured_urls.append(url)
            return mock_response

        with patch("httpx.post", side_effect=capture_post):
            app._count_reminders(
                "postgres://myuser:mypass@ep-cool-mouse.us-east-2.aws.neon.tech/neondb",
                "yebyen",
                24,
            )

        assert captured_urls == ["https://ep-cool-mouse.us-east-2.aws.neon.tech/sql"]


# ---------------------------------------------------------------------------
# _parse_query_params — URL query string parsing (new in Phase 1.6)
# ---------------------------------------------------------------------------


class TestParseQueryParams:
    """_parse_query_params() extracts user_id and hours from path+query strings."""

    def test_basic_params(self):
        result = app._parse_query_params(
            "/internal/arabic-skip-count?user_id=yebyen&hours=24"
        )
        assert result == {"user_id": "yebyen", "hours": "24"}

    def test_user_id_only(self):
        result = app._parse_query_params(
            "/internal/arabic-skip-count?user_id=yebyen"
        )
        assert result["user_id"] == "yebyen"
        assert "hours" not in result

    def test_no_query_string(self):
        result = app._parse_query_params("/internal/arabic-skip-count")
        assert result == {}

    def test_empty_string(self):
        result = app._parse_query_params("")
        assert result == {}

    def test_none_input(self):
        result = app._parse_query_params(None)
        assert result == {}

    def test_default_hours_missing(self):
        """Caller is responsible for defaulting hours to 24 when absent."""
        result = app._parse_query_params(
            "/internal/arabic-skip-count?user_id=alice"
        )
        assert result.get("hours") is None

    def test_extra_params_included(self):
        """Unknown query params are passed through (caller ignores them)."""
        result = app._parse_query_params(
            "/internal/arabic-skip-count?user_id=bob&hours=12&debug=1"
        )
        assert result["user_id"] == "bob"
        assert result["hours"] == "12"
        assert result["debug"] == "1"


# ---------------------------------------------------------------------------
# _json_response / _error_json — serialization helpers
# ---------------------------------------------------------------------------


class TestResponseHelpers:
    """_json_response and _error_json produce valid JSON bytes."""

    def test_json_response_structure(self):
        import json

        result = app._json_response(7)
        data = json.loads(result)
        assert data == {"skip_count": 7}

    def test_json_response_zero(self):
        import json

        result = app._json_response(0)
        assert json.loads(result) == {"skip_count": 0}

    def test_error_json_structure(self):
        import json

        result = app._error_json("user_id is required")
        data = json.loads(result)
        assert data == {"error": "user_id is required"}

    def test_response_is_bytes(self):
        assert isinstance(app._json_response(1), bytes)
        assert isinstance(app._error_json("oops"), bytes)
