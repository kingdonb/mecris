"""Unit tests for scheduler.py: global background job functions and
MecrisScheduler methods not covered by test_scheduler_election.py
or test_scheduler_timer_reset.py.

Covers:
  _global_reminder_job       — non-leader, leader, exception
  _global_language_sync_job  — non-leader, leader
  _global_walk_sync_job      — non-leader, no-NEON, no-pending-walks
  _global_archivist_job      — non-leader, leader
  _global_cooperative_monitor_job — no-NEON
  MecrisScheduler.__init__   — no-NEON raises EnvironmentError
  MecrisScheduler.start      — idempotent, not-running
  MecrisScheduler._init_db   — exception path
  MecrisScheduler._attempt_leadership — no user_id
  MecrisScheduler._stop_leader_jobs   — not running, running
  MecrisScheduler.enqueue_delayed_message — success, exception
  MecrisScheduler.get_queue  — success, exception
  MecrisScheduler.shutdown   — non-leader, leader
"""
import asyncio
import os
import sys
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

# ─── bootstrap: prime sys.modules with scheduler's heavy deps when they are
#     absent (i.e. when this file runs in isolation without test_presence_
#     scheduler.py having run first).  setdefault() is safe — real installs
#     are never clobbered.
# ─────────────────────────────────────────────────────────────────────────────
_SCHEDULER_FAKES = {
    "psycopg2":                         MagicMock(),
    "apscheduler":                      MagicMock(),
    "apscheduler.schedulers":           MagicMock(),
    "apscheduler.schedulers.asyncio":   MagicMock(),
    "apscheduler.triggers":             MagicMock(),
    "apscheduler.triggers.date":        MagicMock(),
    "apscheduler.jobstores":            MagicMock(),
    "apscheduler.jobstores.sqlalchemy": MagicMock(),
}
for _k, _v in _SCHEDULER_FAKES.items():
    sys.modules.setdefault(_k, _v)

if "scheduler" not in sys.modules:
    import scheduler as _scheduler_bootstrap  # noqa: F401 — side-effect import


# ─── helpers ─────────────────────────────────────────────────────────────────

def _fresh_scheduler(**attrs):
    """Return a MecrisScheduler via __new__ with sensible test defaults."""
    import scheduler as _sched
    s = _sched.MecrisScheduler.__new__(_sched.MecrisScheduler)
    s.neon_url = "postgres://fake"
    s.user_id = "u1"
    s.process_id = "pid-test"
    s.is_leader = False
    s.running = False
    s._election_task = None
    s._has_obs_columns = None
    s.scheduler = MagicMock()
    for k, v in attrs.items():
        setattr(s, k, v)
    return s


def _mock_mcp(is_leader=True):
    """Minimal mock of the mcp_server module."""
    m = MagicMock()
    m.scheduler = MagicMock()
    m.scheduler.is_leader = is_leader
    return m


# ═════════════════════════════════════════════════════════════════════════════
# _global_reminder_job
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_global_reminder_job_non_leader_skips():
    """Non-leader: returns early without calling trigger_reminder_check."""
    from scheduler import _global_reminder_job
    mock_mcp = _mock_mcp(is_leader=False)
    trigger = AsyncMock()
    mock_mcp.trigger_reminder_check = trigger
    with patch.dict(sys.modules, {"mcp_server": mock_mcp}):
        await _global_reminder_job("trigger_reminder_check", "u1")
    trigger.assert_not_called()


@pytest.mark.asyncio
async def test_global_reminder_job_leader_calls_trigger():
    """Leader: calls trigger_reminder_check(user_id=..., apply_fuzz=True)."""
    from scheduler import _global_reminder_job
    mock_mcp = _mock_mcp(is_leader=True)
    trigger = AsyncMock(return_value={"triggered": True, "send": {"method": "sms"}})
    mock_mcp.trigger_reminder_check = trigger
    with patch.dict(sys.modules, {"mcp_server": mock_mcp}):
        await _global_reminder_job("trigger_reminder_check", "u1")
    trigger.assert_called_once_with(user_id="u1", apply_fuzz=True)


@pytest.mark.asyncio
async def test_global_reminder_job_exception_does_not_raise():
    """Exception inside the body is caught; function returns normally."""
    from scheduler import _global_reminder_job
    mock_mcp = _mock_mcp(is_leader=True)
    mock_mcp.trigger_reminder_check = AsyncMock(side_effect=RuntimeError("boom"))
    with patch.dict(sys.modules, {"mcp_server": mock_mcp}):
        # Must not propagate
        await _global_reminder_job("trigger_reminder_check", "u1")


# ═════════════════════════════════════════════════════════════════════════════
# _global_language_sync_job
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_global_language_sync_job_non_leader_skips():
    """Non-leader: sync_all is never called."""
    from scheduler import _global_language_sync_job
    mock_mcp = _mock_mcp(is_leader=False)
    mock_mcp.language_sync_service = MagicMock()
    with patch.dict(sys.modules, {"mcp_server": mock_mcp}):
        await _global_language_sync_job("u1")
    mock_mcp.language_sync_service.sync_all.assert_not_called()


@pytest.mark.asyncio
async def test_global_language_sync_job_leader_syncs():
    """Leader: calls sync_all(dry_run=False, user_id=...)."""
    from scheduler import _global_language_sync_job
    mock_mcp = _mock_mcp(is_leader=True)
    mock_mcp.language_sync_service.sync_all = AsyncMock(return_value={"min_safebuf": 5})
    with patch.dict(sys.modules, {"mcp_server": mock_mcp}):
        await _global_language_sync_job("u1")
    mock_mcp.language_sync_service.sync_all.assert_called_once_with(
        dry_run=False, user_id="u1"
    )


# ═════════════════════════════════════════════════════════════════════════════
# _global_walk_sync_job
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_global_walk_sync_job_non_leader_skips():
    """Non-leader: returns before touching NEON_DB_URL or psycopg2."""
    from scheduler import _global_walk_sync_job
    mock_mcp = _mock_mcp(is_leader=False)
    with patch.dict(sys.modules, {"mcp_server": mock_mcp}), \
         patch("scheduler.psycopg2") as mock_pg:
        await _global_walk_sync_job("u1")
    mock_pg.connect.assert_not_called()


@pytest.mark.asyncio
async def test_global_walk_sync_job_no_neon_url_skips():
    """Leader but no NEON_DB_URL: returns before psycopg2 call."""
    from scheduler import _global_walk_sync_job
    mock_mcp = _mock_mcp(is_leader=True)
    mock_mcp.get_user_beeminder_client = MagicMock()
    env_without_neon = {k: v for k, v in os.environ.items() if k != "NEON_DB_URL"}
    with patch.dict(sys.modules, {"mcp_server": mock_mcp}), \
         patch.dict("os.environ", env_without_neon, clear=True), \
         patch("scheduler.psycopg2") as mock_pg:
        await _global_walk_sync_job("u1")
    mock_pg.connect.assert_not_called()


@pytest.mark.asyncio
async def test_global_walk_sync_job_no_pending_walks_returns_early():
    """Leader + NEON_DB_URL set, but DB returns no 'logging' walks: exits before sync."""
    from scheduler import _global_walk_sync_job
    mock_mcp = _mock_mcp(is_leader=True)
    mock_mcp.get_user_beeminder_client = MagicMock()

    mock_psycopg2 = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []
    mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch.dict(sys.modules, {"mcp_server": mock_mcp, "psycopg2": mock_psycopg2}), \
         patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake"}):
        await _global_walk_sync_job("u1")

    mock_cur.fetchall.assert_called_once()
    # Beeminder client should never be called (no walks)
    mock_mcp.get_user_beeminder_client.return_value.add_datapoint.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# _global_archivist_job
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_global_archivist_job_non_leader_skips():
    """Non-leader: ghost.archivist.run is never called."""
    from scheduler import _global_archivist_job
    mock_mcp = _mock_mcp(is_leader=False)
    mock_archivist = MagicMock()
    mock_archivist.run = AsyncMock()
    with patch.dict(sys.modules, {"mcp_server": mock_mcp,
                                   "ghost.archivist": mock_archivist}):
        await _global_archivist_job("u1")
    mock_archivist.run.assert_not_called()


@pytest.mark.asyncio
async def test_global_archivist_job_leader_runs_archivist():
    """Leader: calls ghost.archivist.run(user_id=...)."""
    from scheduler import _global_archivist_job
    mock_mcp = _mock_mcp(is_leader=True)
    mock_archivist = MagicMock()
    mock_archivist.run = AsyncMock()
    mock_ghost = MagicMock()
    with patch.dict(sys.modules, {"mcp_server": mock_mcp,
                                   "ghost": mock_ghost,
                                   "ghost.archivist": mock_archivist}):
        await _global_archivist_job("u1")
    mock_archivist.run.assert_called_once_with(user_id="u1")


# ═════════════════════════════════════════════════════════════════════════════
# _global_cooperative_monitor_job
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_global_cooperative_monitor_job_no_neon_url_skips():
    """Leader but no NEON_DB_URL: returns without any DB activity."""
    from scheduler import _global_cooperative_monitor_job
    mock_mcp = _mock_mcp(is_leader=True)
    env_without_neon = {k: v for k, v in os.environ.items() if k != "NEON_DB_URL"}
    with patch.dict(sys.modules, {"mcp_server": mock_mcp}), \
         patch.dict("os.environ", env_without_neon, clear=True), \
         patch("scheduler.psycopg2") as mock_pg:
        await _global_cooperative_monitor_job("u1")
    mock_pg.connect.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# MecrisScheduler.__init__
# ═════════════════════════════════════════════════════════════════════════════

def test_init_no_neon_url_raises_environment_error():
    """Without NEON_DB_URL in env, __init__ raises EnvironmentError."""
    env_without_neon = {k: v for k, v in os.environ.items() if k != "NEON_DB_URL"}
    with patch.dict("os.environ", env_without_neon, clear=True):
        from scheduler import MecrisScheduler
        with pytest.raises(EnvironmentError, match="NEON_DB_URL"):
            MecrisScheduler(user_id="u1")


# ═════════════════════════════════════════════════════════════════════════════
# MecrisScheduler.start()
# ═════════════════════════════════════════════════════════════════════════════

def test_start_idempotent_when_already_running():
    """start() is a no-op when self.running is already True."""
    s = _fresh_scheduler(running=True)
    with patch.object(s, "_init_db") as mock_init:
        s.start()
    mock_init.assert_not_called()
    assert s._election_task is None  # unchanged


def test_start_when_not_running_initialises_db_and_scheduler():
    """start() calls _init_db, marks running=True, and starts the APScheduler."""
    s = _fresh_scheduler(running=False)
    mock_task = MagicMock()
    with patch.object(s, "_init_db") as mock_init, \
         patch("asyncio.create_task", return_value=mock_task):
        s.start()
    mock_init.assert_called_once()
    assert s.running is True
    s.scheduler.start.assert_called_once()
    assert s._election_task is mock_task


# ═════════════════════════════════════════════════════════════════════════════
# MecrisScheduler._init_db
# ═════════════════════════════════════════════════════════════════════════════

def test_init_db_exception_raises_connection_error():
    """_init_db re-raises psycopg2 failures as ConnectionError."""
    s = _fresh_scheduler()
    with patch("scheduler.psycopg2.connect", side_effect=Exception("db down")):
        with pytest.raises(ConnectionError, match="Neon database"):
            s._init_db()


# ═════════════════════════════════════════════════════════════════════════════
# MecrisScheduler._attempt_leadership
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_attempt_leadership_no_user_id_returns_early():
    """user_id=None: _attempt_leadership returns without any DB calls."""
    s = _fresh_scheduler(user_id=None)
    with patch("scheduler.psycopg2.connect") as mock_connect:
        await s._attempt_leadership()
    mock_connect.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# MecrisScheduler._stop_leader_jobs
# ═════════════════════════════════════════════════════════════════════════════

def test_stop_leader_jobs_when_scheduler_not_running_is_silent():
    """_stop_leader_jobs does not raise when APScheduler is not running."""
    s = _fresh_scheduler()
    s.scheduler.running = False
    # Should complete without raising
    s._stop_leader_jobs()


def test_stop_leader_jobs_removes_all_five_jobs():
    """_stop_leader_jobs calls remove_job for all 5 expected job IDs."""
    s = _fresh_scheduler(user_id="u1")
    s.scheduler.running = True
    s._stop_leader_jobs()
    assert s.scheduler.remove_job.call_count == 5
    job_ids_called = {c.args[0] for c in s.scheduler.remove_job.call_args_list}
    assert "auto_reminder_check_u1" in job_ids_called
    assert "auto_archivist_u1" in job_ids_called


# ═════════════════════════════════════════════════════════════════════════════
# MecrisScheduler.enqueue_delayed_message
# ═════════════════════════════════════════════════════════════════════════════

def test_enqueue_delayed_message_success_returns_job_dict():
    """On first-attempt success, returns dict with job_id and run_at."""
    s = _fresh_scheduler()
    mock_twilio = MagicMock()
    with patch.dict(sys.modules, {"twilio_sender": mock_twilio}):
        result = s.enqueue_delayed_message("hello", 5)
    assert "job_id" in result
    assert "run_at" in result
    s.scheduler.add_job.assert_called_once()


def test_enqueue_delayed_message_exception_returns_error_dict():
    """When add_job raises a non-retryable exception, returns {'error': ...}."""
    s = _fresh_scheduler()
    s.scheduler.add_job.side_effect = Exception("storage error")
    mock_twilio = MagicMock()
    with patch.dict(sys.modules, {"twilio_sender": mock_twilio}):
        result = s.enqueue_delayed_message("hello", 5)
    assert "error" in result


# ═════════════════════════════════════════════════════════════════════════════
# MecrisScheduler.get_queue
# ═════════════════════════════════════════════════════════════════════════════

def test_get_queue_returns_list_of_job_dicts():
    """get_queue serialises APScheduler jobs into a list of dicts."""
    s = _fresh_scheduler()
    mock_job = MagicMock()
    mock_job.id = "job-1"
    mock_job.next_run_time = datetime(2026, 5, 1, tzinfo=timezone.utc)
    mock_job.func_ref = "func"
    s.scheduler.get_jobs.return_value = [mock_job]
    result = s.get_queue()
    assert len(result) == 1
    assert result[0]["id"] == "job-1"
    assert "next_run" in result[0]


def test_get_queue_exception_returns_empty_list():
    """When get_jobs raises, get_queue swallows the error and returns []."""
    s = _fresh_scheduler()
    s.scheduler.get_jobs.side_effect = Exception("scheduler error")
    result = s.get_queue()
    assert result == []


# ═════════════════════════════════════════════════════════════════════════════
# MecrisScheduler.shutdown
# ═════════════════════════════════════════════════════════════════════════════

def test_shutdown_non_leader_skips_neon_cleanup():
    """Non-leader shutdown: no Neon UPDATE; APScheduler.shutdown called."""
    s = _fresh_scheduler(is_leader=False)
    s.scheduler.running = True
    with patch("scheduler.psycopg2.connect") as mock_connect:
        s.shutdown()
    mock_connect.assert_not_called()
    s.scheduler.shutdown.assert_called_once()


def test_shutdown_leader_clears_process_id_in_neon():
    """Leader shutdown: issues UPDATE to clear process_id in Neon."""
    s = _fresh_scheduler(is_leader=True)
    s.scheduler.running = True
    mock_psycopg2 = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    with patch("scheduler.psycopg2", mock_psycopg2):
        s.shutdown()
    update_calls = [c for c in mock_cur.execute.call_args_list if "UPDATE" in str(c)]
    assert len(update_calls) == 1
    assert "process_id" in str(update_calls[0])
    s.scheduler.shutdown.assert_called_once()
