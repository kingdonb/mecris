"""The MCP server's use of the Claude Code status line snapshot (kingdonb/mecris#344)."""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import claude_plan_usage as cpu
import claude_statusline as cs

LOCAL_USER = "local-user"


def _reading(weekly, minutes_ago, source="manual"):
    now = datetime.now(timezone.utc)
    windows = cpu.build_windows(weekly, (now + timedelta(days=2)).isoformat())
    return cpu.make_reading(windows, source=source, observed_at=(now - timedelta(minutes=minutes_ago)).isoformat())


def _write_snapshot(weekly, minutes_ago):
    now = datetime.now(timezone.utc)
    payload = {"session_id": "s1", "rate_limits": {"seven_day": {
        "used_percentage": weekly, "resets_at": int((now + timedelta(days=2)).timestamp())}}}
    cs.write_snapshot(cs.snapshot_path(), cs.build_snapshot(payload, None, now - timedelta(minutes=minutes_ago)))


@pytest.fixture
def server():
    """mcp_server with the plan store, user resolution and Beeminder replaced."""
    with patch.dict(os.environ, {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": LOCAL_USER}):
        with patch("psycopg2.connect", return_value=MagicMock()):
            import mcp_server
    store = MagicMock()
    store.latest.return_value = None
    store.record.return_value = {"recorded": True, "id": 7}
    store.history.return_value = []
    tracker = MagicMock()
    tracker.resolve_user_id.side_effect = lambda u: u
    with patch.object(mcp_server, "_claude_plan_store", store), \
         patch.object(mcp_server, "usage_tracker", tracker), \
         patch.object(mcp_server, "resolve_target_user", side_effect=lambda u: u or LOCAL_USER), \
         patch.object(mcp_server, "get_user_beeminder_client", return_value=AsyncMock()), \
         patch.dict(os.environ, {"CLAUDE_BEEMINDER_GOAL": ""}):
        yield mcp_server, store


class TestStatus:
    def test_newer_snapshot_wins_over_the_stored_reading(self, server):
        mcp_server, store = server
        store.latest.return_value = _reading(23, minutes_ago=120)
        _write_snapshot(31.0, minutes_ago=1)
        status = mcp_server._get_claude_plan_status_sync(LOCAL_USER)
        assert status["source"] == "claude_code_cli"
        assert status["windows"][0]["pct_used"] == 31.0

    def test_newer_stored_reading_wins_over_the_snapshot(self, server):
        mcp_server, store = server
        store.latest.return_value = _reading(40, minutes_ago=1)
        _write_snapshot(31.0, minutes_ago=120)
        assert mcp_server._get_claude_plan_status_sync(LOCAL_USER)["source"] == "manual"

    def test_no_snapshot_is_the_stored_reading(self, server):
        mcp_server, store = server
        store.latest.return_value = _reading(40, minutes_ago=1)
        assert mcp_server._get_claude_plan_status_sync(LOCAL_USER)["windows"][0]["pct_used"] == 40

    def test_another_user_never_sees_this_machines_snapshot(self, server):
        mcp_server, store = server
        _write_snapshot(31.0, minutes_ago=1)
        status = mcp_server._get_claude_plan_status_sync("someone-else")
        assert status["state"] == "unknown"
        assert status["windows"] == []


class TestIngest:
    async def test_first_snapshot_is_stored_for_the_local_user(self, server):
        mcp_server, store = server
        _write_snapshot(31.0, minutes_ago=1)
        result = await mcp_server._ingest_local_claude_reading()
        assert result["recorded"] is True
        user_id, reading = store.record.call_args.args
        assert user_id == LOCAL_USER
        assert reading["source"] == "claude_code_cli"
        assert reading["windows"][0]["pct_used"] == 31.0

    async def test_unchanged_snapshot_is_not_stored_again(self, server):
        mcp_server, store = server
        _write_snapshot(31.0, minutes_ago=1)
        store.latest.return_value = _reading(31.0, minutes_ago=60, source="claude_code_cli")
        result = await mcp_server._ingest_local_claude_reading()
        assert result == {"recorded": False, "reason": "nothing new"}
        store.record.assert_not_called()

    async def test_no_snapshot_stores_nothing(self, server):
        mcp_server, store = server
        result = await mcp_server._ingest_local_claude_reading()
        assert result["recorded"] is False
        store.record.assert_not_called()

    async def test_database_failure_is_reported_not_raised(self, server):
        mcp_server, store = server
        _write_snapshot(31.0, minutes_ago=1)
        store.latest.side_effect = RuntimeError("connection refused to host with secrets")
        result = await mcp_server._ingest_local_claude_reading()
        assert result == {"recorded": False, "error": "RuntimeError"}

    async def test_stored_reading_reaches_the_beeminder_graph(self, server):
        mcp_server, store = server
        _write_snapshot(31.0, minutes_ago=1)
        reading = _reading(31.0, minutes_ago=1, source="claude_code_cli")
        store.history.return_value = [{**reading, "id": 7}]
        with patch.dict(os.environ, {"CLAUDE_BEEMINDER_GOAL": "claude"}):
            result = await mcp_server._ingest_local_claude_reading()
        assert result["beeminder"]["pushed"] is True
        assert result["beeminder"]["value"] == 31


class TestRecordTool:
    async def test_manual_recording_still_returns_status_and_beeminder(self, server):
        mcp_server, store = server
        reset = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        result = await mcp_server.record_claude_plan_usage(50, reset, user_id=LOCAL_USER)
        assert result["recorded"] is True
        assert result["status"]["state"] == "available"
        assert result["beeminder"] == {"pushed": False, "reason": "CLAUDE_BEEMINDER_GOAL not set"}

    async def test_storage_error_is_returned(self, server):
        mcp_server, store = server
        store.record.side_effect = RuntimeError("boom")
        reset = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        result = await mcp_server.record_claude_plan_usage(50, reset, user_id=LOCAL_USER)
        assert result == {"recorded": False, "error": "boom"}
