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


async def _run_narrator_context_with_aggregate(aggregate_result, claude_plan=None, budget_status=None,
                                               presence=None, beeminder_goals=None, env=None,
                                               scheduler_attrs=None, mocks_out=None):
    """Helper: run get_narrator_context with all deps mocked + a specific aggregate result."""
    sys.modules.pop("mcp_server", None)
    mocks = _narrator_patches(aggregate_result)
    if budget_status is not None:
        mocks["mock_tracker"].get_budget_status.return_value = budget_status
    for name, value in (scheduler_attrs or {}).items():
        setattr(mocks["mock_scheduler"], name, value)
    if mocks_out is not None:
        mocks_out.update(mocks)
    environ = {**_base_env(), **(env or {})}

    with patch.dict("os.environ", environ):
        import os as _os
        if "MECRIS_GHOST_ENABLED" not in (env or {}):
            _os.environ.pop("MECRIS_GHOST_ENABLED", None)
        with patch("psycopg2.connect"):
            with patch("mcp_server.usage_tracker", mocks["mock_tracker"]):
                with patch("mcp_server.resolve_target_user", return_value="test-user"):
                    with patch("mcp_server._record_presence", AsyncMock()):
                        with patch("mcp_server.obsidian_client") as mock_obsidian:
                            mock_obsidian.get_todos = AsyncMock(return_value=[])
                            with patch("mcp_server.get_cached_beeminder_goals", AsyncMock(return_value=beeminder_goals or [])):
                                with patch("mcp_server.get_user_beeminder_client", return_value=mocks["mock_beeminder_client"]):
                                    with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value={"status": "done", "has_activity_today": True})):
                                        with patch("mcp_server.get_groq_context_for_narrator", return_value={}):
                                            with patch("mcp_server.neon_checker", mocks["mock_neon"]):
                                                with patch("mcp_server.language_sync_service", mocks["mock_lang_sync"]):
                                                    with patch("mcp_server.weather_service", mocks["mock_weather"]):
                                                        with patch("mcp_server.scheduler", mocks["mock_scheduler"]):
                                                            with patch("mcp_server._neon_budget_governor", mocks["mock_governor"]):
                                                                with patch("mcp_server._get_presence_summary", AsyncMock(return_value=presence or {})):
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


# Status line readings (#383): source claude_code_cli, UTC offsets, fractional
# percentages, no weekly_fable, minutes old.

def _status_line_row(weekly, session=None, minutes_old=7):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    windows = [{"kind": "weekly_all", "pct_used": weekly,
                "resets_at": (now + timedelta(days=2)).isoformat()}]  # "+00:00", as the status line writes it
    if session is not None:
        windows.append({"kind": "session", "pct_used": session,
                        "resets_at": (now + timedelta(hours=2)).isoformat()})
    return {"plan": "ultra", "verified": False, "windows": windows, "source": "claude_code_cli",
            "observed_at": (now - timedelta(minutes=minutes_old)).isoformat(), "notes": "Claude Code status line"}


def test_get_claude_plan_status_reads_a_status_line_row():
    sys.modules.pop("mcp_server", None)
    row = _status_line_row(26.0, session=30.0)
    assert row["windows"][0]["resets_at"].endswith("+00:00")
    with patch.dict("os.environ", _base_env()), patch("psycopg2.connect"):
        import mcp_server
        with patch("mcp_server.resolve_target_user", return_value="test-user"), \
             patch.object(mcp_server.usage_tracker, "resolve_user_id", return_value="test-user"), \
             patch.object(mcp_server._claude_plan_store, "latest", return_value=row):
            status = mcp_server.get_claude_plan_status()
    assert status["state"] == "available" and status["stale"] is False
    assert status["source"] == "claude_code_cli"
    assert status["reason"] == "session at 30%"
    assert status["summary_line"].startswith("Claude: available (26% weekly, resets ")


@pytest.mark.asyncio
async def test_narrator_status_line_80_5_is_constrained_and_printed_as_80():
    import claude_plan_usage as cpu
    plan = cpu.summarize(_status_line_row(80.5, session=40.0))
    result = await _run_narrator_context_with_aggregate(_AGG, claude_plan=plan)
    assert result["claude_plan"]["source"] == "claude_code_cli"
    assert "Claude: constrained (80% weekly, resets " in result["summary"]
    assert any("weekly_all at 80%" in r for r in result["recommendations"])
    assert not any("stale" in r for r in result["recommendations"])
    assert not any("CLAUDE" in u for u in result["urgent_items"])


@pytest.mark.asyncio
async def test_narrator_status_line_session_exhausted_without_weekly_fable_is_urgent():
    import claude_plan_usage as cpu
    plan = cpu.summarize(_status_line_row(64.0, session=100.0, minutes_old=2))
    result = await _run_narrator_context_with_aggregate(_AGG, claude_plan=plan)
    assert any("CLAUDE PLAN EXHAUSTED: session at 100%" in u for u in result["urgent_items"])
    assert "Claude: exhausted (64% weekly, resets " in result["summary"]


@pytest.mark.asyncio
async def test_subscription_phrase_with_a_fractional_status_line_reading():
    import claude_plan_usage as cpu
    plan = cpu.summarize(_status_line_row(23.5))
    result = await _run_narrator_context_with_aggregate(_AGG, claude_plan=plan, budget_status=_subscription())
    assert "Claude: Ultra until 2027-05-13, available (24% weekly, resets " in result["summary"]
    assert result["summary"].count("Claude:") == 1


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
    # The reset has to be ahead of the real clock: the tool reports the reading's
    # state, and a reading whose week has already ended is "unknown".
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    resets_at = (now + timedelta(days=3)).isoformat()
    stored = [{"id": 5, "plan": "ultra", "observed_at": now.isoformat(),
               "windows": [{"kind": "weekly_all", "pct_used": 12, "resets_at": resets_at}]}]
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
            result = await mcp_server.record_claude_plan_usage(12, resets_at)
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
async def test_record_reading_pushes_the_weekly_percentage_to_configured_goal():
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


# ---------------------------------------------------------------------------
# Truthful pulse in the narrator (#346)
# ---------------------------------------------------------------------------

_OLD_GHOST = {"status": "active_human", "ghost_age_seconds": 1647 * 3600.0}


@pytest.mark.asyncio
async def test_no_ghost_recommendation_while_flag_unset():
    result = await _run_narrator_context_with_aggregate(_AGG, presence=_OLD_GHOST)
    assert not any("Ghost" in r for r in result["recommendations"])


@pytest.mark.asyncio
async def test_ghost_recommendation_returns_when_flag_set():
    result = await _run_narrator_context_with_aggregate(_AGG, presence=_OLD_GHOST,
                                                       env={"MECRIS_GHOST_ENABLED": "1"})
    assert any("Ghost Heartbeat" in r for r in result["recommendations"])


@pytest.mark.asyncio
async def test_system_pulse_reports_standby_as_state():
    result = await _run_narrator_context_with_aggregate(
        _AGG, scheduler_attrs={"is_leader": False, "leader_process_id": "other0001",
                               "role_state": "standby", "last_status": "standby (leader other0001)",
                               "intent": "standby", "last_error": None})
    pulse = result["system_pulse"]
    assert pulse["state"] == "standby"
    assert pulse["leader_process_id"] == "other0001"
    assert pulse["last_error"] is None


def _agg_with_akamai(bad_key, total):
    return {**_AGG, "system_pulse": {"modalities": [
        {"role": "AKAMAI FUNCTIONS", "status": "healthy", "minutes_since": 20,
         "refusals_today": total, "bad_key_refusals_today": bad_key}]}}


@pytest.mark.asyncio
async def test_bad_key_cron_refusal_is_one_urgent_item():
    result = await _run_narrator_context_with_aggregate(_agg_with_akamai(2, 5))
    hits = [u for u in result["urgent_items"] if "bad_key" in u]
    assert len(hits) == 1
    assert "AKAMAI" in hits[0]


@pytest.mark.asyncio
async def test_burned_key_probes_raise_nothing():
    result = await _run_narrator_context_with_aggregate(_agg_with_akamai(0, 3))
    assert not any("AKAMAI" in u for u in result["urgent_items"])


# ---------------------------------------------------------------------------
# Paused or due-later Beeminder goals are not urgent derail risk (#346 fold-in)
# ---------------------------------------------------------------------------

def _goal(slug, risk, safebuf=0, due=0, road=100, yaw=1, rate=1.0):
    return {"slug": slug, "title": slug, "safebuf": safebuf, "derail_risk": risk, "rate": rate,
            "yaw": yaw, "beeminder_road_today": road, "beeminder_due_today": due,
            "current_value": 100.0, "target_value": 200.0, "runits": "d", "pledge": 5.0}


@pytest.mark.asyncio
async def test_goal_with_nothing_due_today_is_not_derailing():
    mocks = {}
    goals = [_goal("ellinika", "CRITICAL", due=0), _goal("bike", "CRITICAL", due=3)]
    result = await _run_narrator_context_with_aggregate(_AGG, beeminder_goals=goals, mocks_out=mocks)
    assert "DERAILING: bike" in result["urgent_items"]
    assert "DERAILING: ellinika" not in result["urgent_items"]
    passed = mocks["mock_beeminder_client"].get_runway_summary.call_args.kwargs["all_goals"]
    risks = {g["slug"]: g["derail_risk"] for g in passed}
    assert risks == {"ellinika": "DUE_LATER", "bike": "CRITICAL"}


@pytest.mark.asyncio
async def test_paused_goal_is_not_derailing():
    mocks = {}
    goals = [_goal("bike", "CRITICAL", rate=0.0, road=None, due=0)]
    result = await _run_narrator_context_with_aggregate(_AGG, beeminder_goals=goals, mocks_out=mocks)
    assert not any(u.startswith("DERAILING") for u in result["urgent_items"])
    passed = mocks["mock_beeminder_client"].get_emergencies.call_args.args[0]
    assert passed[0]["derail_risk"] == "PAUSED"


@pytest.mark.asyncio
async def test_unknown_road_keeps_critical():
    goals = [_goal("reviewstack", "CRITICAL", road=None, due=0)]
    result = await _run_narrator_context_with_aggregate(_AGG, beeminder_goals=goals)
    assert "DERAILING: reviewstack" in result["urgent_items"]


# ---------------------------------------------------------------------------
# Claude Ultra subscription in the narrator (kingdonb/mecris#345)
# ---------------------------------------------------------------------------

_PLAN = {"state": "available", "summary_line": "Claude: available (3% weekly, resets Mon 4:00 AM)",
         "observed_at": "2026-11-14T05:06:00+00:00"}


def _subscription(health="GOOD", days=180, since=0):
    alerts = {"GOOD": [], "ENDING": ["GRANT_ENDING"], "ENDED": ["GRANT_ENDED"]}[health]
    return {"source_type": "subscription", "plan": "ultra", "budget_health": health, "alerts": alerts,
            "grant_end": "2027-05-13", "period_end": "2027-05-13", "days_to_grant_end": days,
            "days_remaining": days, "days_since_grant_end": since, "period_expired": False,
            "remaining_budget": 20.72, "total_budget": 20.72}


def _mentions(result, text):
    return sum(text in line for line in result["urgent_items"] + result["recommendations"])


@pytest.mark.asyncio
async def test_subscription_merges_grant_and_plan_into_one_claude_phrase():
    result = await _run_narrator_context_with_aggregate(_AGG, claude_plan=_PLAN, budget_status=_subscription())
    assert "Claude: Ultra until 2027-05-13, available (3% weekly, resets Mon 4:00 AM)" in result["summary"]
    assert result["summary"].count("Claude:") == 1
    assert "Budget:" not in result["summary"]


@pytest.mark.asyncio
async def test_live_subscription_raises_no_budget_nag():
    result = await _run_narrator_context_with_aggregate(_AGG, claude_plan=_PLAN, budget_status=_subscription(days=2))
    assert _mentions(result, "update_budget") == 0
    assert not any("BUDGET" in u for u in result["urgent_items"])
    assert not any("budget constraints" in r for r in result["recommendations"])


@pytest.mark.asyncio
async def test_ending_grant_is_one_recommendation():
    result = await _run_narrator_context_with_aggregate(
        _AGG, claude_plan=_PLAN, budget_status=_subscription("ENDING", days=10))
    hits = [r for r in result["recommendations"] if "grant ends 2027-05-13" in r]
    assert len(hits) == 1
    assert not any("GRANT" in u for u in result["urgent_items"])


@pytest.mark.asyncio
async def test_ended_grant_appears_exactly_once():
    result = await _run_narrator_context_with_aggregate(
        _AGG, claude_plan=_PLAN, budget_status=_subscription("ENDED", days=0, since=3))
    assert _mentions(result, "GRANT ENDED") == 1
    assert any("GRANT ENDED" in u for u in result["urgent_items"])
    assert "Claude: Ultra ended 2027-05-13" in result["summary"]


@pytest.mark.asyncio
async def test_retired_budget_is_quiet():
    retired = {"source_type": "retired", "budget_health": "RETIRED", "alerts": [], "period_expired": False,
               "days_remaining": 0, "remaining_budget": 20.72, "total_budget": 20.72}
    result = await _run_narrator_context_with_aggregate(_AGG, claude_plan=_PLAN, budget_status=retired)
    assert "Budget: retired" in result["summary"]
    assert "Claude: available (3% weekly" in result["summary"]
    assert _mentions(result, "update_budget") == 0
    assert not any("BUDGET" in u for u in result["urgent_items"])
