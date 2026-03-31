"""
Tests for mecris-go-spin/arabic-skip-counter/app.py

Validates the WIT binding class (WitWorld) against the same scenarios as
test_arabic_skip_count.py.  Tests run against the Python source directly
(not the compiled WASM) — componentize-py wraps this same logic.
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


@pytest.fixture
def component():
    """Import and return a fresh WitWorld instance from app.py."""
    import importlib
    # Re-import to get a clean instance each test
    import app
    importlib.reload(app)
    return app.WitWorld()


class TestWitWorldInterface:
    """WitWorld class satisfies the WIT count-arabic-reminders export signature."""

    def test_has_count_arabic_reminders(self, component):
        assert hasattr(component, "count_arabic_reminders")
        assert callable(component.count_arabic_reminders)

    def test_returns_int(self):
        """Returns an int (u32 in WIT) on successful Neon response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": [{"count": "5"}]}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.post", return_value=mock_response):
            import app
            result = app.WitWorld().count_arabic_reminders(
                "postgres://user:pw@host.neon.tech/db", "yebyen", 24
            )
        assert isinstance(result, int)
        assert result == 5

    def test_returns_zero_on_error(self):
        """Returns 0 (never raises) on HTTP failure — fail-safe."""
        with patch("httpx.post", side_effect=Exception("network error")):
            import app
            result = app.WitWorld().count_arabic_reminders(
                "postgres://user:pw@host.neon.tech/db", "yebyen", 24
            )
        assert result == 0

    def test_returns_zero_on_empty_rows(self):
        """Returns 0 when Neon returns an empty rows list."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": []}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.post", return_value=mock_response):
            import app
            result = app.WitWorld().count_arabic_reminders(
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
            import app
            app.WitWorld().count_arabic_reminders(
                "postgres://user:pw@host.neon.tech/db", "yebyen", 48
            )

        assert len(captured_params) == 1
        params = captured_params[0]
        # params[0] = type1, params[1] = type2, params[2] = user_id, params[3] = cutoff
        assert params[2] == "yebyen"
        # cutoff should be a timestamp string (ISO format)
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
            import app
            app.WitWorld().count_arabic_reminders(
                "postgres://myuser:mypass@ep-cool-mouse.us-east-2.aws.neon.tech/neondb",
                "yebyen",
                24,
            )

        assert captured_urls == ["https://ep-cool-mouse.us-east-2.aws.neon.tech/sql"]
