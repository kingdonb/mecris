"""Standby is a state, not an error (#346).

Leadership flips after macOS dark wakes are normal failover. A process that
is not the leader reports 'standby (leader <pid>)' with no last_error, and the
leader shown anywhere (get_system_health, /health, the narrator) is the
process named in the scheduler_election row, not the caller's own id.

Only labels change here; the in-job imports in scheduler.py are untouched.
"""
import datetime
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_ENV = {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user", "MECRIS_MODE": "standalone"}


@pytest.fixture
def sched():
    with patch.dict("os.environ", _ENV):
        from scheduler import MecrisScheduler
        s = MecrisScheduler(user_id="test-user")
        s.scheduler = MagicMock()
        s.neon_url = "postgres://fake"
        s.process_id = "me000001"
        yield s


def _db(rowcount, leader_row):
    psycopg2 = MagicMock()
    conn, cur = MagicMock(), MagicMock()
    psycopg2.connect.return_value.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cur
    cur.rowcount = rowcount
    cur.fetchone.return_value = leader_row
    return psycopg2, cur


@pytest.mark.asyncio
async def test_losing_leadership_reads_as_standby_not_error(sched):
    psycopg2, cur = _db(0, ("other0001", datetime.datetime.now()))
    sched.is_leader = True
    sched._has_obs_columns = True
    with patch("scheduler.psycopg2", psycopg2), patch.object(sched, "_stop_leader_jobs", MagicMock()):
        await sched._attempt_leadership()
    assert sched.is_leader is False
    assert sched.last_status == "standby (leader other0001)"
    assert sched.intent == "standby"
    assert sched.last_error is None
    assert sched.leader_process_id == "other0001"
    for call in cur.execute.call_args_list:
        assert "preempted" not in str(call)


@pytest.mark.asyncio
async def test_standby_label_survives_missing_obs_columns(sched):
    psycopg2, _ = _db(0, ("other0001", datetime.datetime.now()))
    sched.is_leader = True
    sched._has_obs_columns = False
    with patch("scheduler.psycopg2", psycopg2), patch.object(sched, "_stop_leader_jobs", MagicMock()):
        await sched._attempt_leadership()
    assert sched.last_status == "standby (leader other0001)"
    assert sched.last_error is None


@pytest.mark.asyncio
async def test_process_that_never_led_reports_standby(sched):
    psycopg2, _ = _db(0, ("other0001", datetime.datetime.now()))
    sched.is_leader = False
    sched.last_error = "preempted by stale"
    with patch("scheduler.psycopg2", psycopg2):
        await sched._attempt_leadership()
    assert sched.last_status == "standby (leader other0001)"
    assert sched.intent == "standby"
    assert sched.last_error is None
    assert sched.leader_process_id == "other0001"


@pytest.mark.asyncio
async def test_elected_process_names_itself_leader(sched):
    psycopg2, _ = _db(1, None)
    sched._has_obs_columns = True
    with patch("scheduler.psycopg2", psycopg2), patch.object(sched, "_start_leader_jobs", AsyncMock()):
        await sched._attempt_leadership()
    assert sched.is_leader is True
    assert sched.leader_process_id == "me000001"


def test_role_state(sched):
    sched.is_leader, sched.leader_process_id = True, "me000001"
    assert sched.role_state == "leader"
    sched.is_leader, sched.leader_process_id = False, "other0001"
    assert sched.role_state == "standby"
    sched.is_leader, sched.leader_process_id = False, None
    assert sched.role_state == "starting"


# ---------------------------------------------------------------------------
# Server surfaces
# ---------------------------------------------------------------------------

@pytest.fixture
def server():
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", _ENV), patch("psycopg2.connect"):
        import mcp_server
        yield mcp_server
    sys.modules.pop("mcp_server", None)


@pytest.mark.asyncio
async def test_system_health_reports_the_database_leader(server):
    checker_result = {"processes": [], "overall_status": "healthy", "leader_process_id": "dbleader1"}
    with patch.object(server, "resolve_target_user", return_value="test-user"), \
         patch.object(server._health_checker, "get_system_health", return_value=checker_result), \
         patch.object(server.scheduler, "process_id", "me000001"), \
         patch.object(server.scheduler, "is_leader", False):
        result = await server.get_system_health("test-user")
    assert result["leader_process_id"] == "dbleader1"
    assert result["this_process_id"] == "me000001"
    assert result["is_leader"] is False


def test_health_endpoint_reports_the_database_leader(server):
    from fastapi.testclient import TestClient
    conn, cur = MagicMock(), MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.__enter__.return_value = conn
    cur.fetchone.return_value = ("dbleader1",)
    with patch("psycopg2.connect", return_value=conn), \
         patch.object(server.scheduler, "process_id", "me000001"):
        body = TestClient(server.app, client=("127.0.0.1", 5000)).get("/health").json()
    assert body["leader_pid"] == "dbleader1"
    assert body["this_pid"] == "me000001"


def test_cli_heartbeat_shows_standby_as_a_state():
    from cli.pulse import _heartbeat_text
    text = _heartbeat_text({"running": True, "is_leader": False, "state": "standby",
                            "leader_process_id": "other0001", "process_id": "me000001",
                            "last_error": None}, {"score": "1/3"})
    assert "standby (leader other0001)" in text
    assert "error" not in text.lower()
    assert "DOWN" not in text
