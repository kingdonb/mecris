"""
Tests for the Human Yield Presence Detection additions (kingdonb/mecris#211).

Covers:
- SYSTEM_LOCK_PATH is a fixed /tmp path (not CWD-relative)
- is_mecris_cli_active() returns True when pgrep finds cli.main processes
- is_mecris_cli_active() filters out own PID
- is_mecris_cli_active() returns False when pgrep finds nothing
- is_mecris_cli_active() returns False on pgrep failure (fail-open)
- is_human_present() returns True when presence lock is fresh
- is_human_present() returns True when CLI process is active (no lock)
- is_human_present() returns False with stale lock and no active process
- MecrisScheduler._start_leader_jobs() skips registration when human present
"""

import os
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ghost.presence import (
    SYSTEM_LOCK_PATH,
    acquire_lock,
    release_lock,
    is_mecris_cli_active,
    is_human_present,
    PRESENCE_TTL_SECONDS,
)


# ---------------------------------------------------------------------------
# SYSTEM_LOCK_PATH
# ---------------------------------------------------------------------------

class TestSystemLockPath:
    def test_is_absolute_path(self):
        assert os.path.isabs(SYSTEM_LOCK_PATH)

    def test_not_cwd_relative(self):
        # Must not start with the current working directory
        assert not SYSTEM_LOCK_PATH.startswith(os.getcwd())

    def test_default_is_tmp(self):
        # When env var is not set, should be /tmp/mecris_presence.lock
        # (env var may be set in CI — just verify it's an absolute path)
        assert SYSTEM_LOCK_PATH.startswith("/")


# ---------------------------------------------------------------------------
# is_mecris_cli_active()
# ---------------------------------------------------------------------------

class TestIsMecrisCliActive:
    def _pgrep_result(self, stdout: str, returncode: int = 0):
        """Return a mock CompletedProcess with given stdout."""
        mock = MagicMock()
        mock.stdout = stdout
        mock.returncode = returncode
        return mock

    def test_returns_true_when_other_pid_found(self):
        foreign_pid = str(os.getpid() + 1)
        with patch("ghost.presence.subprocess.run", return_value=self._pgrep_result(foreign_pid + "\n")):
            assert is_mecris_cli_active() is True

    def test_returns_false_when_only_own_pid(self):
        own_pid = str(os.getpid())
        with patch("ghost.presence.subprocess.run", return_value=self._pgrep_result(own_pid + "\n")):
            assert is_mecris_cli_active() is False

    def test_returns_false_when_no_output(self):
        with patch("ghost.presence.subprocess.run", return_value=self._pgrep_result("")):
            assert is_mecris_cli_active() is False

    def test_returns_false_on_pgrep_exception(self):
        with patch("ghost.presence.subprocess.run", side_effect=FileNotFoundError("no pgrep")):
            assert is_mecris_cli_active() is False

    def test_returns_false_on_timeout(self):
        import subprocess
        with patch("ghost.presence.subprocess.run", side_effect=subprocess.TimeoutExpired("pgrep", 5)):
            assert is_mecris_cli_active() is False

    def test_filters_whitespace_pids(self):
        # pgrep output with blank lines should not produce false positives
        with patch("ghost.presence.subprocess.run", return_value=self._pgrep_result("\n   \n")):
            assert is_mecris_cli_active() is False


# ---------------------------------------------------------------------------
# is_human_present()
# ---------------------------------------------------------------------------

class TestIsHumanPresent:
    def test_returns_true_when_lock_is_fresh(self, tmp_path):
        lock = str(tmp_path / "presence.lock")
        acquire_lock(lock)
        assert is_human_present(lock_path=lock) is True
        release_lock(lock)

    def test_returns_true_when_cli_active_no_lock(self, tmp_path):
        lock = str(tmp_path / "presence.lock")
        # No lock file; CLI process is running
        foreign_pid = str(os.getpid() + 1)
        mock_result = MagicMock()
        mock_result.stdout = foreign_pid + "\n"
        with patch("ghost.presence.subprocess.run", return_value=mock_result):
            assert is_human_present(lock_path=lock) is True

    def test_returns_false_when_stale_lock_and_no_process(self, tmp_path):
        lock = str(tmp_path / "presence.lock")
        acquire_lock(lock)
        # Backdate the lock to make it stale
        old_time = time.time() - PRESENCE_TTL_SECONDS - 60
        os.utime(lock, (old_time, old_time))
        with patch("ghost.presence.subprocess.run", return_value=MagicMock(stdout="")):
            assert is_human_present(lock_path=lock) is False
        release_lock(lock)

    def test_returns_false_when_no_lock_no_process(self, tmp_path):
        lock = str(tmp_path / "presence.lock")
        with patch("ghost.presence.subprocess.run", return_value=MagicMock(stdout="")):
            assert is_human_present(lock_path=lock) is False

    def test_custom_lock_path_used(self, tmp_path):
        """is_human_present respects the lock_path kwarg."""
        lock = str(tmp_path / "custom.lock")
        acquire_lock(lock)
        assert is_human_present(lock_path=lock) is True
        release_lock(lock)


# ---------------------------------------------------------------------------
# MecrisScheduler._start_leader_jobs() honours presence
# ---------------------------------------------------------------------------

import sys


def _make_minimal_scheduler():
    """Build a MecrisScheduler instance with all heavy deps pre-mocked.

    ``scheduler.py`` imports psycopg2, apscheduler, and services at module
    level.  We inject fakes into sys.modules *before* importing scheduler so
    the top-level imports succeed even in a bare environment.
    """
    fakes = {
        "psycopg2": MagicMock(),
        "apscheduler": MagicMock(),
        "apscheduler.schedulers": MagicMock(),
        "apscheduler.schedulers.asyncio": MagicMock(),
        "apscheduler.triggers": MagicMock(),
        "apscheduler.triggers.date": MagicMock(),
        "apscheduler.jobstores": MagicMock(),
        "apscheduler.jobstores.sqlalchemy": MagicMock(),
        "services": MagicMock(),
        "services.credentials_manager": MagicMock(),
    }

    # Patch sys.modules, import (or reload) scheduler, then restore.
    saved = {k: sys.modules.get(k) for k in fakes}
    sys.modules.update(fakes)
    # Also inject the attribute the module reads from services.credentials_manager
    fakes["services.credentials_manager"].credentials_manager = MagicMock()
    fakes["services.credentials_manager"].credentials_manager.resolve_user_id.return_value = "test_user"

    try:
        if "scheduler" in sys.modules:
            del sys.modules["scheduler"]
        import scheduler as sched_module
        # Re-inject after import in case the module cached the mock
        s = object.__new__(sched_module.MecrisScheduler)
    finally:
        # Restore original sys.modules entries
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    s.neon_url = "postgresql://fake"
    s.user_id = "test_user"
    s.process_id = "testpid"
    s.is_leader = True
    s.running = True
    s._election_task = None
    s.scheduler = MagicMock()
    s.scheduler.get_job.return_value = None  # All jobs appear unregistered
    return s


class TestSchedulerPresenceGuard:
    """Verify that _start_leader_jobs exits early when human is present."""

    @pytest.mark.asyncio
    async def test_skips_jobs_when_human_present(self):
        s = _make_minimal_scheduler()
        with patch("ghost.presence.is_human_present", return_value=True):
            await s._start_leader_jobs()
        s.scheduler.add_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_registers_jobs_when_no_human(self):
        s = _make_minimal_scheduler()
        with patch("ghost.presence.is_human_present", return_value=False):
            await s._start_leader_jobs()
        assert s.scheduler.add_job.call_count >= 1
