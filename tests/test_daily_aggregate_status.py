"""
Tests for get_daily_aggregate_status MCP tool (kingdonb/mecris#170 — The Majesty Cake backend).

Covers:
- Walk goal satisfied when has_activity_today is True
- Walk goal unsatisfied when has_activity_today is False
- Arabic and Greek review pump: goal_met=True → satisfied
- Arabic and Greek review pump: goal_met=False → unsatisfied
- all_clear=True only when all three goals are satisfied
- Partial completion returns correct satisfied_count/total_count
- Language data missing → goal marked unsatisfied with error
- Walk check exception → goal marked unsatisfied with error
"""

import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def _base_patches():
    return [
        patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}),
        patch("psycopg2.connect"),
    ]


def _make_lang_stats(arabic_goal_met: bool, greek_goal_met: bool):
    return {
        "arabic": {"goal_met": arabic_goal_met, "status": "laminar", "target_flow_rate": 0, "current_flow_rate": 5},
        "greek": {"goal_met": greek_goal_met, "status": "laminar", "target_flow_rate": 0, "current_flow_rate": 10},
    }


@pytest.mark.asyncio
async def test_all_goals_satisfied_returns_all_clear():
    """When walk + arabic + greek all done, all_clear=True and score=3/3."""
    sys.modules.pop("mcp_server", None)
    walk_result = {"has_activity_today": True, "source": "neon_cloud"}
    lang_result = _make_lang_stats(arabic_goal_met=True, greek_goal_met=True)

    env_patch, db_patch = _base_patches()
    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value=walk_result)):
                with patch("mcp_server.get_language_velocity_stats", AsyncMock(return_value=lang_result)):
                    from mcp_server import get_daily_aggregate_status
                    result = await get_daily_aggregate_status()

    assert result["all_clear"] is True
    assert result["satisfied_count"] == 3
    assert result["total_count"] == 3
    assert result["score"] == "3/3"


@pytest.mark.asyncio
async def test_no_walk_returns_partial():
    """Walk not done, both languages done → satisfied_count=2, all_clear=False."""
    sys.modules.pop("mcp_server", None)
    walk_result = {"has_activity_today": False, "source": "neon_cloud"}
    lang_result = _make_lang_stats(arabic_goal_met=True, greek_goal_met=True)

    env_patch, db_patch = _base_patches()
    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value=walk_result)):
                with patch("mcp_server.get_language_velocity_stats", AsyncMock(return_value=lang_result)):
                    from mcp_server import get_daily_aggregate_status
                    result = await get_daily_aggregate_status()

    assert result["all_clear"] is False
    assert result["satisfied_count"] == 2
    assert result["score"] == "2/3"
    walk_goal = next(g for g in result["goals"] if g["name"] == "daily_walk")
    assert walk_goal["satisfied"] is False


@pytest.mark.asyncio
async def test_arabic_not_done_returns_partial():
    """Walk done, arabic not done, greek done → satisfied_count=2, all_clear=False."""
    sys.modules.pop("mcp_server", None)
    walk_result = {"has_activity_today": True, "source": "beeminder"}
    lang_result = _make_lang_stats(arabic_goal_met=False, greek_goal_met=True)

    env_patch, db_patch = _base_patches()
    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value=walk_result)):
                with patch("mcp_server.get_language_velocity_stats", AsyncMock(return_value=lang_result)):
                    from mcp_server import get_daily_aggregate_status
                    result = await get_daily_aggregate_status()

    assert result["all_clear"] is False
    assert result["satisfied_count"] == 2
    arabic_goal = next(g for g in result["goals"] if g["name"] == "arabic_review")
    assert arabic_goal["satisfied"] is False


@pytest.mark.asyncio
async def test_nothing_done_returns_zero():
    """Nothing done → satisfied_count=0, score=0/3, all_clear=False."""
    sys.modules.pop("mcp_server", None)
    walk_result = {"has_activity_today": False, "source": "neon_cloud"}
    lang_result = _make_lang_stats(arabic_goal_met=False, greek_goal_met=False)

    env_patch, db_patch = _base_patches()
    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value=walk_result)):
                with patch("mcp_server.get_language_velocity_stats", AsyncMock(return_value=lang_result)):
                    from mcp_server import get_daily_aggregate_status
                    result = await get_daily_aggregate_status()

    assert result["all_clear"] is False
    assert result["satisfied_count"] == 0
    assert result["score"] == "0/3"


@pytest.mark.asyncio
async def test_missing_language_data_marks_unsatisfied():
    """If a language is absent from velocity stats, that goal is unsatisfied with error."""
    sys.modules.pop("mcp_server", None)
    walk_result = {"has_activity_today": True, "source": "neon_cloud"}
    # Only arabic present, no greek
    lang_result = {
        "arabic": {"goal_met": True, "status": "laminar"},
    }

    env_patch, db_patch = _base_patches()
    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value=walk_result)):
                with patch("mcp_server.get_language_velocity_stats", AsyncMock(return_value=lang_result)):
                    from mcp_server import get_daily_aggregate_status
                    result = await get_daily_aggregate_status()

    greek_goal = next(g for g in result["goals"] if g["name"] == "greek_review")
    assert greek_goal["satisfied"] is False
    assert "error" in greek_goal
    assert result["satisfied_count"] == 2  # walk + arabic


@pytest.mark.asyncio
async def test_walk_exception_marks_unsatisfied():
    """If walk check raises, walk goal is unsatisfied with error, others still evaluated."""
    sys.modules.pop("mcp_server", None)
    lang_result = _make_lang_stats(arabic_goal_met=True, greek_goal_met=True)

    env_patch, db_patch = _base_patches()
    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            with patch("mcp_server.get_cached_daily_activity", AsyncMock(side_effect=RuntimeError("DB down"))):
                with patch("mcp_server.get_language_velocity_stats", AsyncMock(return_value=lang_result)):
                    from mcp_server import get_daily_aggregate_status
                    result = await get_daily_aggregate_status()

    walk_goal = next(g for g in result["goals"] if g["name"] == "daily_walk")
    assert walk_goal["satisfied"] is False
    assert "error" in walk_goal
    # Arabic and Greek still evaluated
    assert result["satisfied_count"] == 2
    assert result["all_clear"] is False


@pytest.mark.asyncio
async def test_result_contains_required_keys():
    """Result always contains goals, satisfied_count, total_count, all_clear, score."""
    sys.modules.pop("mcp_server", None)
    walk_result = {"has_activity_today": True, "source": "neon_cloud"}
    lang_result = _make_lang_stats(arabic_goal_met=True, greek_goal_met=True)

    env_patch, db_patch = _base_patches()
    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value=walk_result)):
                with patch("mcp_server.get_language_velocity_stats", AsyncMock(return_value=lang_result)):
                    from mcp_server import get_daily_aggregate_status
                    result = await get_daily_aggregate_status()

    for key in ("goals", "satisfied_count", "total_count", "all_clear", "score"):
        assert key in result, f"Missing key: {key}"
    assert isinstance(result["goals"], list)
    assert len(result["goals"]) == 3
