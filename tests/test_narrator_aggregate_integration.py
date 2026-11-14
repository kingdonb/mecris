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


async def _run_narrator_context_with_aggregate(aggregate_result, claude_plan=None, budget_status=None):
    """Helper: run get_narrator_context with all deps mocked + a specific aggregate result."""
    sys.modules.pop("mcp_server", None)
    mocks = _narrator_patches(aggregate_result)
    if budget_status is not None:
        mocks["mock_tracker"].get_budget_status.return_value = budget_status

    with patch.dict("os.environ", _base_env()):
        with patch("psycopg2.connect"):
            with patch("mcp_server.usage_tracker", mocks["mock_tracker"]):
                with patch("mcp_server.resolve_target_user", return_value="test-user"):
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
                                                            with patch("mcp_server._neon_budget_governor", mocks["mock_governor"]):
                                                                with patch("mcp_server._get_presence_summary", AsyncMock(return_value={})):
                                                                    with patch("mcp_server.anthropic_cost_tracker", None):
                                                                        with patch("mcp_server.get_daily_aggregate_status", AsyncMock(return_value=aggregate_result)):
                                                                            with patch("mcp_server._get_claude_plan_status_sync", return_value=claude_plan or {}):
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


@pytest.mark.asyncio
async def test_narrator_all_clear_cake_is_first_recommendation():
    """When all_clear=True and no critical items, Majesty Cake is the first recommendation."""
    aggregate = {"score": "3/3", "satisfied_count": 3, "total_count": 3, "all_clear": True, "goals": []}
    result = await _run_narrator_context_with_aggregate(aggregate)
    recommendations = result.get("recommendations", [])
    assert recommendations, "Expected at least one recommendation"
    assert "Majesty Cake" in recommendations[0], (
        f"Expected Majesty Cake as first recommendation, got: {recommendations}"
    )


@pytest.mark.asyncio
async def test_narrator_partial_progress_precedes_informational_recommendations():
    """When partial and no critical items (no budget/beeminder/walk alerts), progress rec is first."""
    aggregate = {"score": "1/3", "satisfied_count": 1, "total_count": 3, "all_clear": False, "goals": []}
    result = await _run_narrator_context_with_aggregate(aggregate)
    recommendations = result.get("recommendations", [])
    assert recommendations, "Expected at least one recommendation"
    progress_idx = next((i for i, r in enumerate(recommendations) if "Daily goals progress" in r), None)
    assert progress_idx is not None, f"Progress recommendation not found in: {recommendations}"
    # In the test environment (no budget/beeminder/backlog warnings), progress should be first
    assert progress_idx == 0, (
        f"Expected progress rec at index 0, got index {progress_idx}: {recommendations}"
    )


# ---------------------------------------------------------------------------
# Claude plan availability (kingdonb/mecris#344)
# ---------------------------------------------------------------------------

_AGG = {"score": "1/3", "satisfied_count": 1, "total_count": 3, "all_clear": False, "goals": []}


@pytest.mark.asyncio
async def test_narrator_includes_claude_plan_and_summary_line():
    plan = {"state": "available", "summary_line": "Claude: available (62% weekly, resets Mon 4:00 AM)",
            "observed_at": "2026-11-13T20:00:00+00:00"}
    result = await _run_narrator_context_with_aggregate(_AGG, claude_plan=plan)
    assert result["claude_plan"]["state"] == "available"
    assert "Claude: available (62% weekly" in result["summary"]
    assert not any("CLAUDE" in u for u in result["urgent_items"])


@pytest.mark.asyncio
async def test_narrator_exhausted_claude_plan_is_urgent():
    plan = {"state": "exhausted", "reason": "weekly_all at 100%", "summary_line": "Claude: exhausted (100% weekly, resets Mon 4:00 AM)"}
    result = await _run_narrator_context_with_aggregate(_AGG, claude_plan=plan)
    assert any("CLAUDE PLAN EXHAUSTED" in u for u in result["urgent_items"])


@pytest.mark.asyncio
async def test_narrator_stale_claude_reading_nudges_not_alarms():
    plan = {"state": "unknown", "reason": "reading is stale", "summary_line": "Claude: unknown (reading is stale)",
            "observed_at": "2026-11-10T20:00:00+00:00"}
    result = await _run_narrator_context_with_aggregate(_AGG, claude_plan=plan)
    assert not any("CLAUDE" in u for u in result["urgent_items"])
    assert any("record_claude_plan_usage" in r for r in result["recommendations"])


def test_get_claude_plan_status_failure_reports_unknown():
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", _base_env()), patch("psycopg2.connect"):
        from mcp_server import get_claude_plan_status
        with patch("mcp_server.resolve_target_user", return_value="test-user"), \
             patch("mcp_server._get_claude_plan_status_sync", side_effect=RuntimeError("db down")):
            status = get_claude_plan_status()
    assert status["state"] == "unknown"
    assert "db down" in status["error"]


# ---------------------------------------------------------------------------
# Budget false alarms (kingdonb/mecris#345)
# ---------------------------------------------------------------------------

_EXPIRED = {"days_remaining": 0, "period_expired": True, "days_since_period_end": 37,
            "period_end": "2026-10-07", "budget_health": "STALE", "alerts": ["PERIOD_EXPIRED"]}


@pytest.mark.asyncio
async def test_expired_budget_period_raises_no_budget_alarm():
    result = await _run_narrator_context_with_aggregate(_AGG, budget_status=_EXPIRED)
    assert not any("BUDGET" in u for u in result["urgent_items"])
    assert not any("budget constraints" in r for r in result["recommendations"])
    assert "period ended 2026-10-07 (stale)" in result["summary"]
    assert "days left" not in result["summary"]
    assert any("update_budget" in r for r in result["recommendations"])


@pytest.mark.asyncio
async def test_budget_read_failure_is_unknown_not_critical():
    result = await _run_narrator_context_with_aggregate(_AGG, budget_status={"error": "no row"})
    assert not any("BUDGET" in u for u in result["urgent_items"])
    assert "Budget: unknown" in result["summary"]


@pytest.mark.asyncio
async def test_live_budget_near_end_still_alarms():
    live = {"days_remaining": 1, "period_expired": False, "remaining_budget": 3.0}
    result = await _run_narrator_context_with_aggregate(_AGG, budget_status=live)
    assert any("BUDGET CRITICAL" in u for u in result["urgent_items"])
    assert "Budget: 1.0 days left" in result["summary"]


# ---------------------------------------------------------------------------
# Beeminder graph of Claude plan usage (kingdonb/mecris#371)
# ---------------------------------------------------------------------------

async def _record_reading(goal_env, add_datapoint):
    """Call the record tool with the store and Beeminder client mocked."""
    sys.modules.pop("mcp_server", None)
    env = _base_env()
    if goal_env is not None:
        env["CLAUDE_BEEMINDER_GOAL"] = goal_env
    stored = [{"id": 5, "plan": "ultra", "observed_at": "2026-11-13T20:00:00+00:00",
               "windows": [{"kind": "weekly_all", "pct_used": 12, "resets_at": "2026-11-16T04:00:00-05:00"}]}]
    client = MagicMock()
    client.add_datapoint = add_datapoint
    with patch.dict("os.environ", env, clear=False), patch("psycopg2.connect"):
        import os as _os
        if goal_env is None:
            _os.environ.pop("CLAUDE_BEEMINDER_GOAL", None)
        import mcp_server
        with patch("mcp_server.resolve_target_user", return_value="test-user"), \
             patch.object(mcp_server.usage_tracker, "resolve_user_id", return_value="test-user"), \
             patch.object(mcp_server._claude_plan_store, "record", return_value={"recorded": True, "id": 5}), \
             patch.object(mcp_server._claude_plan_store, "history", return_value=stored) as history, \
             patch("mcp_server.get_user_beeminder_client", return_value=client):
            result = await mcp_server.record_claude_plan_usage(12, "2026-11-16T04:00:00-05:00")
    return result, history


@pytest.mark.asyncio
async def test_record_reading_without_goal_makes_no_beeminder_call():
    add = AsyncMock(return_value=True)
    result, history = await _record_reading(None, add)
    assert result["recorded"] is True
    assert result["beeminder"]["pushed"] is False
    add.assert_not_called()
    history.assert_not_called()


@pytest.mark.asyncio
async def test_record_reading_pushes_running_total_to_configured_goal():
    add = AsyncMock(return_value=True)
    result, _ = await _record_reading("claude-usage", add)
    assert result["beeminder"] == {"pushed": True, "goal": "claude-usage", "value": 12, "requestid": "claude-plan-5"}
    assert add.call_args.args[:2] == ("claude-usage", 12)
    assert add.call_args.kwargs["requestid"] == "claude-plan-5"


@pytest.mark.asyncio
async def test_beeminder_failure_does_not_fail_the_recording():
    add = AsyncMock(side_effect=RuntimeError("beeminder down: response body"))
    result, _ = await _record_reading("claude-usage", add)
    assert result["recorded"] is True and result["status"]["state"] == "available"
    assert result["beeminder"]["pushed"] is False
    assert "response body" not in str(result["beeminder"])
