"""
Tests for Majesty Cake discoverability in get_narrator_context (kingdonb/mecris#170).

Verifies that get_daily_aggregate_status is called from within get_narrator_context,
its result appears as daily_aggregate_status in the response, and an appropriate
recommendation is appended based on the score.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def _base_env():
    return {
        "NEON_DB_URL": "postgres://fake",
        "DEFAULT_USER_ID": "test-user",
    }


def _make_mock_beeminder_client():
    client = MagicMock()
    client.get_emergencies = AsyncMock(return_value=[])
    client.get_runway_summary = AsyncMock(return_value=[])
    return client


def _make_mock_tracker():
    tracker = MagicMock()
    tracker.resolve_user_id.return_value = "test-user"
    tracker.get_goals.return_value = []
    tracker.get_budget_status.return_value = {"days_remaining": 5.0, "remaining_budget": 10.0}
    return tracker


def _make_mock_neon():
    neon = MagicMock()
    neon.get_language_stats.return_value = {
        "arabic": {"next_7_days": 0},
        "greek": {"next_7_days": 0},
    }
    neon.get_latest_walk.return_value = None
    return neon


def _narrator_patches(aggregate_result):
    """Return a dict of all patches needed to run get_narrator_context in isolation."""
    mock_tracker = _make_mock_tracker()
    mock_beeminder_client = _make_mock_beeminder_client()
    mock_neon = _make_mock_neon()
    mock_lang_sync = MagicMock()
    mock_lang_sync._greek_backlog_active.return_value = False
    mock_weather = MagicMock()
    mock_weather.get_weather.return_value = {}
    mock_weather.is_walk_appropriate.return_value = (True, "Weather fine")
    mock_scheduler = MagicMock()
    mock_scheduler.running = True
    mock_scheduler.is_leader = True
    mock_scheduler.process_id = "test-pid"
    mock_governor = MagicMock()
    mock_governor.get_narrator_summary.return_value = {}

    return {
        "mock_tracker": mock_tracker,
        "mock_beeminder_client": mock_beeminder_client,
        "mock_neon": mock_neon,
        "mock_lang_sync": mock_lang_sync,
        "mock_weather": mock_weather,
        "mock_scheduler": mock_scheduler,
        "mock_governor": mock_governor,
    }


async def _run_narrator_context_with_aggregate(aggregate_result):
    """Helper: run get_narrator_context with all deps mocked + a specific aggregate result."""
    sys.modules.pop("mcp_server", None)
    mocks = _narrator_patches(aggregate_result)

    with patch.dict("os.environ", _base_env()):
        with patch("psycopg2.connect"):
            with patch("mcp_server.usage_tracker", mocks["mock_tracker"]):
                with patch("mcp_server._record_presence", AsyncMock()):
                    with patch("mcp_server.obsidian_client") as mock_obsidian:
                        mock_obsidian.get_todos = AsyncMock(return_value=[])
                        with patch("mcp_server.get_cached_beeminder_goals", AsyncMock(return_value=[])):
                            with patch("mcp_server.get_user_beeminder_client", return_value=mocks["mock_beeminder_client"]):
                                with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value={"status": "done", "has_activity_today": True})):
                                    with patch("mcp_server.get_groq_context_for_narrator", return_value={}):
                                        with patch("mcp_server.neon_checker", mocks["mock_neon"]):
                                            with patch("mcp_server.language_sync_service", mocks["mock_lang_sync"]):
                                                with patch("mcp_server.weather_service", mocks["mock_weather"]):
                                                    with patch("mcp_server.scheduler", mocks["mock_scheduler"]):
                                                        with patch("mcp_server._budget_governor", mocks["mock_governor"]):
                                                            with patch("mcp_server._get_presence_status", AsyncMock(return_value={})):
                                                                with patch("mcp_server.anthropic_cost_tracker", None):
                                                                    with patch("mcp_server.get_daily_aggregate_status", AsyncMock(return_value=aggregate_result)):
                                                                        from mcp_server import get_narrator_context
                                                                        return await get_narrator_context()


@pytest.mark.asyncio
async def test_narrator_includes_daily_aggregate_status_key():
    """get_narrator_context result contains daily_aggregate_status key."""
    aggregate = {"score": "2/3", "satisfied_count": 2, "total_count": 3, "all_clear": False, "goals": []}
    result = await _run_narrator_context_with_aggregate(aggregate)
    assert "daily_aggregate_status" in result
    assert result["daily_aggregate_status"]["score"] == "2/3"


@pytest.mark.asyncio
async def test_narrator_partial_score_adds_progress_recommendation():
    """When not all_clear, a progress recommendation mentioning the score is added."""
    aggregate = {"score": "1/3", "satisfied_count": 1, "total_count": 3, "all_clear": False, "goals": []}
    result = await _run_narrator_context_with_aggregate(aggregate)
    recommendations = result.get("recommendations", [])
    assert any("1/3" in r for r in recommendations), f"Expected '1/3' in recommendations: {recommendations}"


@pytest.mark.asyncio
async def test_narrator_all_clear_adds_majesty_cake_recommendation():
    """When all_clear=True, a Majesty Cake celebration recommendation is added."""
    aggregate = {"score": "3/3", "satisfied_count": 3, "total_count": 3, "all_clear": True, "goals": []}
    result = await _run_narrator_context_with_aggregate(aggregate)
    recommendations = result.get("recommendations", [])
    assert any("Majesty Cake" in r or "3/3" in r for r in recommendations), (
        f"Expected Majesty Cake celebration in recommendations: {recommendations}"
    )


@pytest.mark.asyncio
async def test_narrator_aggregate_error_does_not_crash_context():
    """If get_daily_aggregate_status returns an error dict, narrator context still succeeds."""
    aggregate = {"error": "DB down"}
    result = await _run_narrator_context_with_aggregate(aggregate)
    assert "summary" in result
    assert result["daily_aggregate_status"]["error"] == "DB down"
    # No progress or cake recommendation added when error
    recommendations = result.get("recommendations", [])
    assert not any("Majesty Cake" in r for r in recommendations)
    assert not any("Daily goals progress" in r for r in recommendations)
