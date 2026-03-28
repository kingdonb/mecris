import pytest
import sys
from unittest.mock import patch


def _make_mcp_importable():
    """Patch env + psycopg2 so mcp_server can be imported without a real DB."""
    return [
        patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}),
        patch("psycopg2.connect"),
    ]


@pytest.mark.asyncio
async def test_get_coaching_insight_high_momentum_critical():
    # Mock context where walk is done and there's a critical goal
    sys.modules.pop("mcp_server", None)

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
    }
    mock_goals = [
        {"slug": "urgent-goal", "title": "Urgent Goal", "derail_risk": "CRITICAL"}
    ]

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.get_narrator_context", return_value=mock_context), \
             patch("mcp_server.get_cached_beeminder_goals", return_value=mock_goals):
            from mcp_server import get_coaching_insight

            insight = await get_coaching_insight()

            assert insight["type"] == "momentum_pivot"
            assert insight["momentum"] == "high"
            assert "Great job on the walk" in insight["message"]
            assert "Urgent Goal" in insight["message"]
            assert insight["target_slug"] == "urgent-goal"


@pytest.mark.asyncio
async def test_get_coaching_insight_no_walk_critical():
    # Mock context where walk is NOT done and there's a critical goal
    sys.modules.pop("mcp_server", None)

    mock_context = {
        "daily_walk_status": {"has_activity_today": False},
    }
    mock_goals = [
        {"slug": "urgent-goal", "title": "Urgent Goal", "derail_risk": "CRITICAL"}
    ]

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.get_narrator_context", return_value=mock_context), \
             patch("mcp_server.get_cached_beeminder_goals", return_value=mock_goals):
            from mcp_server import get_coaching_insight

            insight = await get_coaching_insight()

            assert insight["type"] == "urgency_alert"
            assert insight["momentum"] == "low"
            assert "Urgent Goal" in insight["message"]
            assert "A quick walk" in insight["message"]


@pytest.mark.asyncio
async def test_get_coaching_insight_neutral():
    # Mock context where walk is NOT done and goals are safe
    sys.modules.pop("mcp_server", None)

    mock_context = {
        "daily_walk_status": {"has_activity_today": False},
    }
    mock_goals = [
        {"slug": "safe-goal", "title": "Safe Goal", "derail_risk": "SAFE"}
    ]

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.get_narrator_context", return_value=mock_context), \
             patch("mcp_server.get_cached_beeminder_goals", return_value=mock_goals):
            from mcp_server import get_coaching_insight

            insight = await get_coaching_insight()

            assert insight["type"] == "walk_prompt"
            assert insight["momentum"] == "neutral"
            assert "ready when you are" in insight["message"]


@pytest.mark.asyncio
async def test_get_coaching_insight_obsidian_context():
    # Mock context with Obsidian activity
    sys.modules.pop("mcp_server", None)

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
    }
    mock_goals = []
    mock_obsidian_activity = "Worked on Mecris architecture"

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.get_narrator_context", return_value=mock_context), \
             patch("mcp_server.get_cached_beeminder_goals", return_value=mock_goals), \
             patch("mcp_server.obsidian_client.get_daily_note", return_value=mock_obsidian_activity):
            from mcp_server import get_coaching_insight

            insight = await get_coaching_insight()

            assert "Mecris" in insight["message"]
            assert insight["type"] == "obsidian_pivot"
