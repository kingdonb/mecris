"""Unit tests for WeatherService — is_walk_appropriate() branches and get_weather() paths.

All tests are pure (no network, no DB, no Spin host). Covers yebyen/mecris#163.
"""
import os
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.weather_service import WeatherService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _good_weather(**overrides):
    """Return a minimal weather dict that passes all walk conditions."""
    now = int(datetime.now().timestamp())
    base = {
        "temperature": 72.0,
        "is_raining": False,
        "is_snowing": False,
        "wind_speed": 5.0,
        "sunrise": now - 3600,   # 1 hour ago
        "sunset":  now + 3600,   # 1 hour from now
        "source": "test",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# is_walk_appropriate — logic branches
# ---------------------------------------------------------------------------

class TestIsWalkAppropriate:
    def setup_method(self):
        self.ws = WeatherService()

    def test_good_conditions_returns_true(self):
        ok, msg = self.ws.is_walk_appropriate(_good_weather())
        assert ok is True
        assert "good" in msg.lower()

    def test_error_with_no_temperature_returns_false(self):
        weather = {"error": "API failure", "source": "error"}
        ok, msg = self.ws.is_walk_appropriate(weather)
        assert ok is False
        assert "unavailable" in msg.lower()

    def test_none_temperature_returns_false(self):
        ok, msg = self.ws.is_walk_appropriate(_good_weather(temperature=None))
        assert ok is False
        assert "temperature" in msg.lower()

    def test_too_cold_returns_false(self):
        ok, msg = self.ws.is_walk_appropriate(_good_weather(temperature=15))
        assert ok is False
        assert "cold" in msg.lower()

    def test_boundary_cold_exactly_20_is_false(self):
        # temp < 20 is the condition, so 20 should NOT trigger cold
        ok, msg = self.ws.is_walk_appropriate(_good_weather(temperature=20))
        assert ok is True

    def test_too_hot_returns_false(self):
        ok, msg = self.ws.is_walk_appropriate(_good_weather(temperature=100))
        assert ok is False
        assert "hot" in msg.lower()

    def test_boundary_hot_exactly_95_is_ok(self):
        # temp > 95 is the condition, so 95 should NOT trigger hot
        ok, msg = self.ws.is_walk_appropriate(_good_weather(temperature=95))
        assert ok is True

    def test_raining_returns_false(self):
        ok, msg = self.ws.is_walk_appropriate(_good_weather(is_raining=True))
        assert ok is False
        assert "rain" in msg.lower()

    def test_too_windy_returns_false(self):
        ok, msg = self.ws.is_walk_appropriate(_good_weather(wind_speed=35))
        assert ok is False
        assert "wind" in msg.lower()

    def test_boundary_wind_exactly_30_is_ok(self):
        # wind_speed > 30 is the condition, so 30 is safe
        ok, msg = self.ws.is_walk_appropriate(_good_weather(wind_speed=30))
        assert ok is True

    def test_before_sunrise_returns_false(self):
        now = int(datetime.now().timestamp())
        ok, msg = self.ws.is_walk_appropriate(_good_weather(sunrise=now + 7200))
        assert ok is False
        assert "early" in msg.lower() or "sun" in msg.lower()

    def test_after_sunset_returns_false(self):
        now = int(datetime.now().timestamp())
        ok, msg = self.ws.is_walk_appropriate(_good_weather(sunset=now - 3600))
        assert ok is False
        assert "late" in msg.lower() or "sun" in msg.lower()

    def test_zero_sunrise_and_sunset_does_not_block(self):
        """sunrise=0 and sunset=0 means no daylight data — should not block."""
        ok, msg = self.ws.is_walk_appropriate(_good_weather(sunrise=0, sunset=0))
        assert ok is True

    def test_error_with_temperature_present_is_evaluated_normally(self):
        """Stale data includes 'error' key but still has temperature — should evaluate conditions."""
        now = int(datetime.now().timestamp())
        stale = {
            "temperature": 72.0,
            "is_raining": False,
            "wind_speed": 5.0,
            "sunrise": now - 3600,
            "sunset":  now + 3600,
            "error": "stale",
            "stale": True,
            "source": "openweather-3.0",
        }
        ok, msg = self.ws.is_walk_appropriate(stale)
        assert ok is True


# ---------------------------------------------------------------------------
# get_weather — mock/cache paths
# ---------------------------------------------------------------------------

class TestGetWeatherMockAndCache:
    def test_mock_mode_returns_mock_data(self):
        with patch.dict(os.environ, {"MOCK_WEATHER": "true", "OPENWEATHER_API_KEY": ""}):
            ws = WeatherService()
            data = ws.get_weather()
        assert data["source"] == "mock"
        assert "temperature" in data
        assert "error" not in data

    def test_no_api_key_falls_back_to_mock(self):
        with patch.dict(os.environ, {"MOCK_WEATHER": "false", "OPENWEATHER_API_KEY": ""}):
            ws = WeatherService()
            data = ws.get_weather()
        assert data["source"] == "mock"

    def test_cache_hit_skips_second_fetch(self):
        """Calling get_weather() twice should hit cache on the second call."""
        with patch.dict(os.environ, {"MOCK_WEATHER": "true"}):
            ws = WeatherService()
            first = ws.get_weather()
            # Tamper with cache data to detect whether cache is returned
            ws._cache["data"]["_marker"] = "cached"
            second = ws.get_weather()
        assert second.get("_marker") == "cached"

    def test_expired_cache_refreshes(self):
        """Manually expire the cache; next call should produce fresh data."""
        with patch.dict(os.environ, {"MOCK_WEATHER": "true"}):
            ws = WeatherService()
            _ = ws.get_weather()
            # Force expiry
            ws._cache["expires"] = datetime.now() - timedelta(minutes=1)
            ws._cache["data"]["_marker"] = "stale"
            fresh = ws.get_weather()
        # Fresh mock data won't carry the _marker
        assert fresh.get("_marker") != "stale"

    def test_api_error_with_stale_cache_returns_stale(self):
        """On API failure, if stale cache exists, return it with stale=True."""
        with patch.dict(os.environ, {"MOCK_WEATHER": "false", "OPENWEATHER_API_KEY": "real_key"}):
            ws = WeatherService()
            # Populate cache but mark as expired
            ws._cache = {
                "data": {"temperature": 65.0, "source": "openweather-3.0"},
                "expires": datetime.now() - timedelta(minutes=5),
            }
            with patch("services.weather_service.requests.get", side_effect=Exception("timeout")):
                data = ws.get_weather()
        assert data.get("stale") is True
        assert data["temperature"] == 65.0

    def test_api_error_with_no_cache_returns_error_dict(self):
        """On API failure with no cache at all, return error dict."""
        with patch.dict(os.environ, {"MOCK_WEATHER": "false", "OPENWEATHER_API_KEY": "real_key"}):
            ws = WeatherService()
            with patch("services.weather_service.requests.get", side_effect=Exception("timeout")):
                data = ws.get_weather()
        assert "error" in data
        assert data["source"] == "error"
