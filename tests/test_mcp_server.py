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
            with patch("mcp_server.usage_tracker") as mock_tracker:
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
