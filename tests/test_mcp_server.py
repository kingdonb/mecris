"""
Tests for Ghost Presence Phase 2 — mcp_server.py middleware (yebyen/mecris#70).

Covers:
- _record_presence calls NeonPresenceStore.upsert with ACTIVE_HUMAN when Neon available
- _record_presence is a no-op when get_neon_store returns None (NEON_DB_URL unset)
- get_narrator_context response includes a "presence_status" key
"""

import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from ghost.presence import StatusType


def _make_mcp_importable():
    """Patch env + psycopg2 so mcp_server can be imported without a real DB."""
    return [
        patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}),
        patch("psycopg2.connect"),
    ]


# ---------------------------------------------------------------------------
# _record_presence tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_presence_calls_upsert_with_active_human():
    """_record_presence upserts ACTIVE_HUMAN when NeonPresenceStore is available."""
    sys.modules.pop("mcp_server", None)

    mock_store = MagicMock()
    env_patch, db_patch = _make_mcp_importable()

    with env_patch, db_patch, patch("mcp_server.get_neon_store", return_value=mock_store):
        from mcp_server import _record_presence
        await _record_presence("user1")

    mock_store.upsert.assert_called_once_with("user1", StatusType.ACTIVE_HUMAN, "mcp_server")


@pytest.mark.asyncio
async def test_record_presence_noop_when_no_neon():
    """_record_presence is a no-op when get_neon_store returns None."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()

    with env_patch, db_patch, patch("mcp_server.get_neon_store", return_value=None):
        from mcp_server import _record_presence
        # Should not raise, and no upsert is called (nothing to assert other than no exception)
        await _record_presence("user1")  # passes if no exception


@pytest.mark.asyncio
async def test_record_presence_swallows_exceptions():
    """_record_presence logs and swallows DB errors gracefully."""
    sys.modules.pop("mcp_server", None)

    mock_store = MagicMock()
    mock_store.upsert.side_effect = RuntimeError("DB down")
    env_patch, db_patch = _make_mcp_importable()

    with env_patch, db_patch, patch("mcp_server.get_neon_store", return_value=mock_store):
        from mcp_server import _record_presence
        # Must not raise
        await _record_presence("user1")


# ---------------------------------------------------------------------------
# get_narrator_context presence_status integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_narrator_context_includes_presence_status():
    """get_narrator_context response dict includes the presence_status key."""
    sys.modules.pop("mcp_server", None)

    mock_store = MagicMock()
    mock_presence_record = MagicMock()
    mock_presence_record.status_type = StatusType.ACTIVE_HUMAN
    mock_store.upsert.return_value = mock_presence_record
    mock_store.get.return_value = mock_presence_record

    mock_beem_client = MagicMock()
    mock_beem_client.get_emergencies = AsyncMock(return_value=[])
    mock_beem_client.get_runway_summary = AsyncMock(return_value=[])

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.get_neon_store", return_value=mock_store):
            with patch("mcp_server.usage_tracker") as mock_tracker, \
                 patch("mcp_server.resolve_target_user", return_value="test-user"):
                mock_tracker.resolve_user_id.return_value = "test-user"
                mock_tracker.get_goals.return_value = []
                mock_tracker.get_budget_status.return_value = {"days_remaining": 10}
                with patch("mcp_server.obsidian_client.get_todos", AsyncMock(return_value=[])):
                    with patch("mcp_server.get_cached_beeminder_goals", AsyncMock(return_value=[])):
                        with patch("mcp_server.get_user_beeminder_client", return_value=mock_beem_client):
                            with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value={"status": "completed", "has_activity_today": True})):
                                with patch("mcp_server.get_groq_context_for_narrator", return_value={}):
                                    with patch("mcp_server.neon_checker.get_language_stats", return_value={}):
                                        with patch("mcp_server.language_sync_service._greek_backlog_active", return_value=False):
                                            with patch("mcp_server.neon_checker.get_latest_walk", return_value=None):
                                                with patch("mcp_server.weather_service.get_weather", return_value={}):
                                                    with patch("mcp_server.weather_service.is_walk_appropriate", return_value=(True, "Good")):
                                                        with patch("mcp_server._budget_governor") as mock_gov:
                                                            mock_gov.get_narrator_summary.return_value = {}
                                                            with patch("mcp_server.scheduler") as mock_sched:
                                                                mock_sched.running = True
                                                                mock_sched.is_leader = False
                                                                mock_sched.process_id = "test"
                                                                with patch("mcp_server.anthropic_cost_tracker", None):
                                                                    from mcp_server import get_narrator_context
                                                                    result = await get_narrator_context()

    assert "presence_status" in result
    assert result["presence_status"] == StatusType.ACTIVE_HUMAN.value


# ---------------------------------------------------------------------------
# GET /languages — sorting and has_goal derivation (kingdonb/mecris#121)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_languages_has_goal_derived_from_beeminder_slug():
    """`has_goal` is True when beeminder_slug is set, False when None/empty."""
    sys.modules.pop("mcp_server", None)

    fake_stats = {
        "arabic": {
            "current": 100, "tomorrow": 90, "next_7_days": 60,
            "daily_rate": 10.0, "safebuf": 2, "derail_risk": "WARNING",
            "multiplier": 1.0, "beeminder_slug": "reviewstack",
        },
        "lithuanian": {
            "current": 50, "tomorrow": 45, "next_7_days": 30,
            "daily_rate": 5.0, "safebuf": 0, "derail_risk": "UNKNOWN",
            "multiplier": 1.0, "beeminder_slug": None,
        },
    }

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.neon_checker.get_language_stats", return_value=fake_stats):
            from mcp_server import get_languages
            result = await get_languages(user_id="test-user")

    langs = {lang["name"]: lang for lang in result["languages"]}
    assert langs["arabic"]["has_goal"] is True
    assert langs["lithuanian"]["has_goal"] is False


@pytest.mark.asyncio
async def test_languages_sorted_beeminder_tracked_first():
    """Languages with beeminder_slug appear before those without in the response."""
    sys.modules.pop("mcp_server", None)

    # Deliberately put untracked language first in the dict to confirm sorting works
    fake_stats = {
        "lithuanian": {
            "current": 50, "tomorrow": 45, "next_7_days": 30,
            "daily_rate": 5.0, "safebuf": 0, "derail_risk": "UNKNOWN",
            "multiplier": 1.0, "beeminder_slug": None,
        },
        "arabic": {
            "current": 100, "tomorrow": 90, "next_7_days": 60,
            "daily_rate": 10.0, "safebuf": 2, "derail_risk": "WARNING",
            "multiplier": 1.0, "beeminder_slug": "reviewstack",
        },
        "greek": {
            "current": 200, "tomorrow": 180, "next_7_days": 120,
            "daily_rate": 20.0, "safebuf": 5, "derail_risk": "OK",
            "multiplier": 1.0, "beeminder_slug": "ellinika",
        },
    }

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.neon_checker.get_language_stats", return_value=fake_stats):
            from mcp_server import get_languages
            result = await get_languages(user_id="test-user")

    lang_list = result["languages"]
    names = [l["name"] for l in lang_list]

    # All has_goal=True languages must precede all has_goal=False languages
    has_goal_flags = [l["has_goal"] for l in lang_list]
    seen_false = False
    for flag in has_goal_flags:
        if not flag:
            seen_false = True
        assert not (seen_false and flag), f"has_goal=True appeared after has_goal=False in: {names}"


# ---------------------------------------------------------------------------
# get_daily_aggregate_status — Majesty Cake backend (kingdonb/mecris#170)
# ---------------------------------------------------------------------------

_FAKE_LANG_STATS_ALL_MET = {
    "arabic": {"goal_met": True, "status": "on_track", "beeminder_slug": "reviewstack"},
    "greek": {"goal_met": True, "status": "on_track", "beeminder_slug": "ellinika"},
}

_FAKE_LANG_STATS_ARABIC_UNMET = {
    "arabic": {"goal_met": False, "status": "derailing", "beeminder_slug": "reviewstack"},
    "greek": {"goal_met": True, "status": "on_track", "beeminder_slug": "ellinika"},
}


@pytest.mark.asyncio
async def test_daily_aggregate_status_schema():
    """get_daily_aggregate_status returns the expected response schema."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value="test-user"):
            with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value={"has_activity_today": True})):
                with patch("mcp_server.get_language_velocity_stats", AsyncMock(return_value=_FAKE_LANG_STATS_ALL_MET)):
                    with patch("mcp_server.usage_tracker.get_budget_status", return_value={"remaining_budget": 10.0}):
                        with patch("mcp_server.neon_checker.get_latest_walk", return_value=None):
                            from mcp_server import get_daily_aggregate_status
                            result = await get_daily_aggregate_status()

    assert "goals" in result
    assert "satisfied_count" in result
    assert "total_count" in result
    assert "all_clear" in result
    assert "score" in result
    assert "components" in result
    assert isinstance(result["goals"], list)
    assert isinstance(result["all_clear"], bool)


@pytest.mark.asyncio
async def test_daily_aggregate_status_all_clear_when_all_goals_met():
    """all_clear=True and satisfied_count==total_count when walk + all languages are satisfied."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value="test-user"):
            with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value={"has_activity_today": True})):
                with patch("mcp_server.get_language_velocity_stats", AsyncMock(return_value=_FAKE_LANG_STATS_ALL_MET)):
                    with patch("mcp_server.usage_tracker.get_budget_status", return_value={"remaining_budget": 10.0}):
                        with patch("mcp_server.neon_checker.get_latest_walk", return_value=None):
                            from mcp_server import get_daily_aggregate_status
                            result = await get_daily_aggregate_status()

    assert result["all_clear"] is True
    assert result["satisfied_count"] == result["total_count"]
    assert result["components"]["walk"] is True
    assert result["components"]["arabic"] is True
    assert result["components"]["greek"] is True


@pytest.mark.asyncio
async def test_daily_aggregate_status_not_all_clear_when_walk_missing():
    """all_clear=False when walk is not satisfied, even if language goals are met."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value="test-user"):
            with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value={"has_activity_today": False})):
                with patch("mcp_server.get_language_velocity_stats", AsyncMock(return_value=_FAKE_LANG_STATS_ALL_MET)):
                    with patch("mcp_server.usage_tracker.get_budget_status", return_value={"remaining_budget": 10.0}):
                        with patch("mcp_server.neon_checker.get_latest_walk", return_value=None):
                            from mcp_server import get_daily_aggregate_status
                            result = await get_daily_aggregate_status()

    assert result["all_clear"] is False
    assert result["satisfied_count"] < result["total_count"]
    assert result["components"]["walk"] is False
