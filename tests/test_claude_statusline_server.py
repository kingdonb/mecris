"""The MCP server's use of the Claude Code status line snapshot (kingdonb/mecris#344)."""

import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
         patch.object(mcp_server.scheduler, "is_leader", True), \
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


class FakeNeon:
    """Just enough of psycopg2 for ClaudePlanUsageStore, shared by every "process".

    An INSERT stores a row unless its statement carries a WHERE NOT EXISTS guard
    and a row with the same (user_id, source, observed_at) is already there.
    """

    def __init__(self):
        self.rows = []
        self.inserts = []

    def connect(self, *_args, **_kwargs):
        neon = self

        class Cursor:
            result = None

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, params=()):
                text = " ".join(sql.split()).upper()
                if text.startswith("INSERT"):
                    neon.inserts.append(text)
                    user, plan, _verified, windows, source, observed_at = params[:6]
                    key = (user, source, observed_at)
                    if "WHERE NOT EXISTS" in text and any(r["key"] == key for r in neon.rows):
                        self.result = None
                        return
                    neon.rows.append({"id": len(neon.rows) + 1, "key": key, "plan": plan,
                                      "windows": windows, "observed_at": observed_at})
                    self.result = (len(neon.rows),)
                elif text.startswith("SELECT ID, PLAN, WINDOWS, OBSERVED_AT"):
                    self.result = [(r["id"], r["plan"], r["windows"], r["observed_at"])
                                   for r in neon.rows if r["key"][0] == params[0]]

            def fetchone(self):
                return self.result

            def fetchall(self):
                return self.result

        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def cursor(self):
                return Cursor()

        return Connection()


@pytest.fixture
def neon(server):
    """The server with a real ClaudePlanUsageStore over one FakeNeon, and a
    counted Beeminder push. `latest` reads nothing, as when two processes look
    before either has written."""
    mcp_server, _ = server
    fake = FakeNeon()
    store = cpu.ClaudePlanUsageStore("postgres://fake")
    push = AsyncMock(return_value={"pushed": True})
    with patch("psycopg2.connect", side_effect=fake.connect), \
         patch.object(store, "latest", return_value=None), \
         patch.object(mcp_server, "_claude_plan_store", store), \
         patch.object(mcp_server.claude_plan_usage, "sync_reading_to_beeminder", push), \
         patch.dict(os.environ, {"CLAUDE_BEEMINDER_GOAL": "claude"}):
        yield mcp_server, fake, push


class TestOneIngestPerSnapshot:
    """Every mcp_server process starts the ingest loop; Claude Desktop runs three
    (kingdonb/mecris#344). One snapshot must give one row and one push."""

    async def test_a_standby_process_does_not_ingest(self, server):
        mcp_server, store = server
        _write_snapshot(31.0, minutes_ago=1)
        with patch.object(mcp_server.scheduler, "is_leader", False):
            result = await mcp_server._ingest_local_claude_reading()
        assert result == {"recorded": False, "reason": "not the scheduler leader"}
        store.latest.assert_not_called()
        store.record.assert_not_called()

    async def test_standby_and_leader_store_the_snapshot_once(self, neon):
        mcp_server, fake, push = neon
        _write_snapshot(31.0, minutes_ago=1)
        with patch.object(mcp_server.scheduler, "is_leader", False):
            await mcp_server._ingest_local_claude_reading()
        with patch.object(mcp_server.scheduler, "is_leader", True):
            await mcp_server._ingest_local_claude_reading()
        assert len(fake.rows) == 1
        assert push.await_count == 1

    async def test_leadership_is_checked_on_every_tick(self, server):
        mcp_server, store = server
        _write_snapshot(31.0, minutes_ago=1)
        with patch.object(mcp_server.scheduler, "is_leader", False):
            assert (await mcp_server._ingest_local_claude_reading())["recorded"] is False
        with patch.object(mcp_server.scheduler, "is_leader", True):
            assert (await mcp_server._ingest_local_claude_reading())["recorded"] is True
        store.record.assert_called_once()

    async def test_a_duplicate_snapshot_gives_one_row_and_one_push(self, neon):
        # Two leaders across a handover, both reading before either writes.
        mcp_server, fake, push = neon
        _write_snapshot(31.0, minutes_ago=1)
        first = await mcp_server._ingest_local_claude_reading()
        second = await mcp_server._ingest_local_claude_reading()
        assert first["recorded"] is True
        assert second["recorded"] is False
        assert second["beeminder"] == {"pushed": False, "reason": "reading not stored"}
        assert len(fake.rows) == 1
        assert push.await_count == 1


class TestTheLeaderIngests:
    """Leadership is shared by every process that starts the scheduler, so each
    of them must also run the ingest; a leader that never ingests leaves Neon,
    Spin, Android and Beeminder stale (kingdonb/mecris#344)."""

    def test_the_stdio_entrypoint_starts_the_ingest(self, server, monkeypatch, tmp_path):
        mcp_server, _ = server
        monkeypatch.setenv("MCP_STDIO_LOG_FILE", str(tmp_path / "stdio.log"))
        monkeypatch.delitem(sys.modules, "mcp_stdio_server", raising=False)
        with patch("logging.basicConfig"):
            import mcp_stdio_server
        started = []
        with patch.object(mcp_server.scheduler, "start", side_effect=lambda: started.append("scheduler")), \
             patch.object(mcp_server.scheduler, "shutdown"), \
             patch.object(mcp_server, "start_claude_snapshot_ingest", side_effect=lambda: started.append("ingest")), \
             patch.object(mcp_server.mcp, "run_stdio_async", AsyncMock()):
            mcp_stdio_server.main()
        assert started == ["scheduler", "ingest"]

    def test_every_entrypoint_that_starts_the_scheduler_starts_the_ingest(self):
        root = Path(__file__).resolve().parent.parent
        scheduler_start = re.compile(r"^\s*scheduler\.start\(\)", re.MULTILINE)
        ingest_start = re.compile(r"^\s*start_claude_snapshot_ingest\(\)", re.MULTILINE)
        missing = sorted(
            p.name for p in root.glob("*.py")
            if not p.name.startswith("test_")
            and len(scheduler_start.findall(p.read_text())) > len(ingest_start.findall(p.read_text()))
        )
        assert missing == []

    async def test_a_leader_without_a_snapshot_says_so_without_a_query(self, server):
        mcp_server, store = server
        result = await mcp_server._ingest_local_claude_reading()
        assert result == {"recorded": False, "reason": "no status line snapshot"}
        store.latest.assert_not_called()

    async def test_the_loop_logs_each_change_of_outcome(self, server, monkeypatch, caplog):
        mcp_server, _ = server
        monkeypatch.setattr(mcp_server, "CLAUDE_SNAPSHOT_INGEST_SECONDS", 0)
        standby = {"recorded": False, "reason": "not the scheduler leader"}
        ingest = AsyncMock(side_effect=[
            standby, standby, standby,
            {"recorded": True, "id": 7, "beeminder": {"pushed": False}},
            {"recorded": False, "reason": "nothing new"},
            {"recorded": False, "reason": "nothing new"},
            asyncio.CancelledError(),
        ])
        monkeypatch.setattr(mcp_server, "_ingest_local_claude_reading", ingest)
        with caplog.at_level(logging.INFO, logger="mecris"), pytest.raises(asyncio.CancelledError):
            await mcp_server._claude_snapshot_ingest_loop()
        lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Claude snapshot ingest")]
        assert len(lines) == 3
        assert "not the scheduler leader" in lines[0]
        assert "stored" in lines[1]
        assert "nothing new" in lines[2]


class TestIdempotentRecord:
    def test_same_user_source_and_time_is_stored_once_in_one_statement(self):
        fake = FakeNeon()
        store = cpu.ClaudePlanUsageStore("postgres://fake")
        reading = _reading(31.0, minutes_ago=1, source="claude_code_cli")
        with patch("psycopg2.connect", side_effect=fake.connect):
            first = store.record(LOCAL_USER, reading)
            second = store.record(LOCAL_USER, reading)
        assert first == {"recorded": True, "id": 1}
        assert second == {"recorded": False, "reason": "already stored"}
        assert len(fake.inserts) == 2
        assert all("SELECT" in sql and "WHERE NOT EXISTS" in sql for sql in fake.inserts)
        # With the v9 unique index in place, a concurrent twin is skipped, not an error.
        assert all("ON CONFLICT DO NOTHING RETURNING ID" in sql for sql in fake.inserts)

    def test_another_source_at_the_same_time_is_stored(self):
        fake = FakeNeon()
        store = cpu.ClaudePlanUsageStore("postgres://fake")
        reading = _reading(31.0, minutes_ago=1, source="claude_code_cli")
        with patch("psycopg2.connect", side_effect=fake.connect):
            store.record(LOCAL_USER, reading)
            other = store.record(LOCAL_USER, {**reading, "source": "manual"})
        assert other["recorded"] is True
        assert len(fake.rows) == 2
