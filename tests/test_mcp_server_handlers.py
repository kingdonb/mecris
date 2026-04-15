"""
Tests for mcp_server.py handler functions — yebyen/mecris#192.

Covers:
- _record_governor_spend: bucket routing (gemini/groq/helix/anthropic_api) + exception swallow
- get_budget_status: auth guard returns error dict when resolve_target_user is None
- get_budget_status: delegates to usage_tracker.get_budget_status when authenticated
- get_weather_report: returns combined weather + is_appropriate + recommendation
- record_usage_session: happy path records usage and governor spend
- record_usage_session: error path returns error dict when record_usage raises
- record_claude_code_usage: happy path returns recorded=True with estimated_cost
- record_claude_code_usage: error path returns error dict
"""

import sys
import pytest
from unittest.mock import patch, MagicMock


def _make_mcp_importable():
    """Patch env + psycopg2 so mcp_server can be imported without a real DB."""
    return [
        patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}),
        patch("psycopg2.connect"),
    ]


# ---------------------------------------------------------------------------
# _record_governor_spend — bucket routing logic
# ---------------------------------------------------------------------------

def test_record_governor_spend_routes_gemini():
    """Model containing 'gemini' routes to the 'gemini' bucket."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        from mcp_server import _record_governor_spend
        with patch("mcp_server._budget_governor") as mock_gov:
            _record_governor_spend("gemini-1.5-pro", 0.05)
            mock_gov.record_spend.assert_called_once_with("gemini", 0.05)


def test_record_governor_spend_routes_groq():
    """Model containing 'groq' routes to the 'groq' bucket."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        from mcp_server import _record_governor_spend
        with patch("mcp_server._budget_governor") as mock_gov:
            _record_governor_spend("groq-llama3", 0.01)
            mock_gov.record_spend.assert_called_once_with("groq", 0.01)


def test_record_governor_spend_routes_helix():
    """Model with ANTHROPIC_BASE_URL containing 'helix' routes to 'helix' bucket."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        from mcp_server import _record_governor_spend
        with patch("mcp_server._budget_governor") as mock_gov, \
             patch.dict("os.environ", {"ANTHROPIC_BASE_URL": "https://helix.example.com/api"}):
            _record_governor_spend("claude-3-5-sonnet", 0.02)
            mock_gov.record_spend.assert_called_once_with("helix", 0.02)


def test_record_governor_spend_defaults_to_anthropic_api():
    """Non-gemini/groq model without helix URL defaults to 'anthropic_api' bucket."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        from mcp_server import _record_governor_spend
        with patch("mcp_server._budget_governor") as mock_gov, \
             patch.dict("os.environ", {"ANTHROPIC_BASE_URL": ""}):
            _record_governor_spend("claude-3-5-haiku-20241022", 0.001)
            mock_gov.record_spend.assert_called_once_with("anthropic_api", 0.001)


def test_record_governor_spend_swallows_exceptions():
    """_record_governor_spend logs and swallows budget_governor errors gracefully."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        from mcp_server import _record_governor_spend
        with patch("mcp_server._budget_governor") as mock_gov:
            mock_gov.record_spend.side_effect = RuntimeError("governor down")
            # Must not raise
            _record_governor_spend("claude-3-5-haiku", 0.01)


# ---------------------------------------------------------------------------
# get_budget_status — auth guard + delegation
# ---------------------------------------------------------------------------

def test_get_budget_status_returns_auth_error_when_unauthenticated():
    """Returns error dict when resolve_target_user returns None."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value=None):
            from mcp_server import get_budget_status
            result = get_budget_status(user_id="unknown")

    assert "error" in result
    assert "Authentication" in result["error"]


def test_get_budget_status_delegates_to_usage_tracker():
    """Delegates to usage_tracker.get_budget_status when authenticated."""
    sys.modules.pop("mcp_server", None)

    expected = {"days_remaining": 14, "remaining_budget": 9.50}

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value="test-user"), \
             patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.get_budget_status.return_value = expected
            from mcp_server import get_budget_status
            result = get_budget_status(user_id="test-user")

    assert result == expected
    mock_tracker.get_budget_status.assert_called_once_with("test-user")


# ---------------------------------------------------------------------------
# get_weather_report — weather_service wrapper
# ---------------------------------------------------------------------------

def test_get_weather_report_returns_combined_dict():
    """Returns dict with 'weather', 'is_appropriate', and 'recommendation' keys."""
    sys.modules.pop("mcp_server", None)

    fake_weather = {"temp": 65, "condition": "Clear"}

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.weather_service") as mock_ws:
            mock_ws.get_weather.return_value = fake_weather
            mock_ws.is_walk_appropriate.return_value = (True, "Great day for a walk!")
            from mcp_server import get_weather_report
            result = get_weather_report()

    assert result["weather"] == fake_weather
    assert result["is_appropriate"] is True
    assert result["recommendation"] == "Great day for a walk!"


def test_get_weather_report_not_appropriate():
    """Returns is_appropriate=False when weather service says no."""
    sys.modules.pop("mcp_server", None)

    fake_weather = {"temp": 20, "condition": "Thunderstorm"}

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.weather_service") as mock_ws:
            mock_ws.get_weather.return_value = fake_weather
            mock_ws.is_walk_appropriate.return_value = (False, "Stay indoors — thunderstorm warning.")
            from mcp_server import get_weather_report
            result = get_weather_report()

    assert result["is_appropriate"] is False
    assert "thunderstorm" in result["recommendation"].lower()


# ---------------------------------------------------------------------------
# record_usage_session — happy path + error path
# ---------------------------------------------------------------------------

def test_record_usage_session_happy_path():
    """Happy path: records usage, calls governor spend, returns recorded=True."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value="test-user"), \
             patch("mcp_server.record_usage", return_value=0.0042) as mock_record, \
             patch("mcp_server._record_governor_spend") as mock_gov, \
             patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.get_budget_status.return_value = {"days_remaining": 10}
            from mcp_server import record_usage_session
            result = record_usage_session(
                input_tokens=1000,
                output_tokens=500,
                model="claude-3-5-haiku-20241022",
                session_type="interactive",
                notes="test session",
                user_id="test-user",
            )

    assert result["recorded"] is True
    assert result["estimated_cost"] == pytest.approx(0.0042)
    assert "updated_status" in result
    mock_record.assert_called_once_with(1000, 500, "claude-3-5-haiku-20241022", "interactive", "test session", "test-user")
    mock_gov.assert_called_once_with("claude-3-5-haiku-20241022", 0.0042)


def test_record_usage_session_auth_error():
    """Returns error dict when resolve_target_user returns None."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value=None):
            from mcp_server import record_usage_session
            result = record_usage_session(input_tokens=100, output_tokens=50)

    assert "error" in result
    assert "Authentication" in result["error"]


def test_record_usage_session_error_path():
    """Returns error dict when record_usage raises an exception."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value="test-user"), \
             patch("mcp_server.record_usage", side_effect=RuntimeError("DB down")):
            from mcp_server import record_usage_session
            result = record_usage_session(input_tokens=100, output_tokens=50)

    assert "error" in result
    assert "Failed to record usage" in result["error"] or "DB down" in result["error"]


# ---------------------------------------------------------------------------
# record_claude_code_usage — happy path + error path
# ---------------------------------------------------------------------------

def test_record_claude_code_usage_happy_path():
    """Happy path: returns recorded=True, estimated_cost, and message."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value="test-user"), \
             patch("mcp_server.record_usage", return_value=0.0015), \
             patch("mcp_server._record_governor_spend"), \
             patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.get_budget_status.return_value = {"days_remaining": 7}
            from mcp_server import record_claude_code_usage
            result = record_claude_code_usage(
                input_tokens=500,
                output_tokens=200,
                model="claude-3-5-haiku",
                notes="CLI session",
                user_id="test-user",
            )

    assert result["recorded"] is True
    assert result["estimated_cost"] == pytest.approx(0.0015)
    assert "message" in result
    assert "0.0015" in result["message"]


def test_record_claude_code_usage_error_path():
    """Returns error dict when record_usage raises an exception."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value="test-user"), \
             patch("mcp_server.record_usage", side_effect=ValueError("bad model")):
            from mcp_server import record_claude_code_usage
            result = record_claude_code_usage(input_tokens=100, output_tokens=50)

    assert "error" in result
