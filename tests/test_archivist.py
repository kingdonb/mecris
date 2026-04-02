"""
Tests for ghost.archivist — presence-aware autonomous pulse logger.

Covers:
- YIELD path: human present → exit 0, log YIELD entry
- PULSE path (online): no human → probe succeeds → log PULSE entry with server_ts
- PULSE path (offline): no human → probe fails → log PULSE entry with error
- Log file is created if it does not exist
- pulse() function returns correct structure on success and failure
- _global_archivist_job: calls archivist_run when leader, skips when not
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from ghost.archivist import run, pulse, DEFAULT_LOG_PATH, DEFAULT_MCP_URL
from ghost.presence import PresenceStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def lock_file(tmp_path):
    return str(tmp_path / "presence.lock")


@pytest.fixture
def log_file(tmp_path):
    return str(tmp_path / "ghost_archivist.log")


def _make_status(human_present: bool, lock_exists: bool = True, age: float = 60.0):
    return PresenceStatus(
        lock_exists=lock_exists,
        human_present=human_present,
        age_seconds=age if lock_exists else None,
        lock_path="/tmp/presence.lock",
    )


# ---------------------------------------------------------------------------
# pulse() unit tests
# ---------------------------------------------------------------------------

class TestPulse:
    def test_online_returns_status_and_server_ts(self):
        fake_body = json.dumps({"status": "ok", "timestamp": "2026-04-02T12:00:00"}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = pulse("http://localhost:8000")

        assert result["status"] == "online"
        assert result["server_ts"] == "2026-04-02T12:00:00"

    def test_offline_returns_error(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            result = pulse("http://localhost:8000")

        assert result["status"] == "offline"
        assert "connection refused" in result["error"]

    def test_offline_on_timeout(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
            result = pulse("http://localhost:9999")

        assert result["status"] == "offline"


# ---------------------------------------------------------------------------
# run() integration tests
# ---------------------------------------------------------------------------

class TestRun:
    def test_yield_when_human_present(self, lock_file, log_file, capsys):
        status = _make_status(human_present=True, age=120.0)

        with patch("ghost.archivist.check_presence", return_value=status):
            rc = run(lock_path=lock_file, log_path=log_file, mcp_url="http://fake:9999")

        assert rc == 0
        captured = capsys.readouterr()
        assert "yielding" in captured.out

        log_content = open(log_file).read()
        assert "[YIELD]" in log_content
        assert "human_present=True" in log_content

    def test_pulse_logged_when_no_human_online(self, lock_file, log_file, capsys):
        status = _make_status(human_present=False, lock_exists=False, age=0)
        online_result = {"status": "online", "server_ts": "2026-04-02T12:00:00"}

        with patch("ghost.archivist.check_presence", return_value=status), \
             patch("ghost.archivist.pulse", return_value=online_result):
            rc = run(lock_path=lock_file, log_path=log_file, mcp_url="http://fake:9999")

        assert rc == 0
        log_content = open(log_file).read()
        assert "[PULSE]" in log_content
        assert "mcp=online" in log_content
        assert "2026-04-02T12:00:00" in log_content

    def test_pulse_logged_when_no_human_offline(self, lock_file, log_file, capsys):
        status = _make_status(human_present=False, lock_exists=False, age=0)
        offline_result = {"status": "offline", "error": "connection refused"}

        with patch("ghost.archivist.check_presence", return_value=status), \
             patch("ghost.archivist.pulse", return_value=offline_result):
            rc = run(lock_path=lock_file, log_path=log_file, mcp_url="http://fake:9999")

        assert rc == 0
        log_content = open(log_file).read()
        assert "[PULSE]" in log_content
        assert "mcp=offline" in log_content
        assert "connection refused" in log_content

    def test_log_file_created_if_missing(self, lock_file, tmp_path):
        log_path = str(tmp_path / "subdir" / "ghost_archivist.log")
        status = _make_status(human_present=False, lock_exists=False, age=0)
        offline_result = {"status": "offline", "error": "server not running"}

        with patch("ghost.archivist.check_presence", return_value=status), \
             patch("ghost.archivist.pulse", return_value=offline_result):
            rc = run(lock_path=lock_file, log_path=log_path, mcp_url="http://fake:9999")

        assert rc == 0
        assert os.path.exists(log_path)

    def test_returns_0_on_yield(self, lock_file, log_file):
        status = _make_status(human_present=True, age=30.0)
        with patch("ghost.archivist.check_presence", return_value=status):
            assert run(lock_path=lock_file, log_path=log_file) == 0

    def test_returns_0_on_pulse(self, lock_file, log_file):
        status = _make_status(human_present=False, lock_exists=False, age=0)
        offline_result = {"status": "offline", "error": "x"}
        with patch("ghost.archivist.check_presence", return_value=status), \
             patch("ghost.archivist.pulse", return_value=offline_result):
            assert run(lock_path=lock_file, log_path=log_file) == 0

    def test_log_entry_has_iso_timestamp(self, lock_file, log_file):
        status = _make_status(human_present=False, lock_exists=False, age=0)
        offline_result = {"status": "offline", "error": "x"}
        with patch("ghost.archivist.check_presence", return_value=status), \
             patch("ghost.archivist.pulse", return_value=offline_result):
            run(lock_path=lock_file, log_path=log_file)

        log_content = open(log_file).read()
        # ISO 8601 UTC timestamp should be present (ends with +00:00)
        assert "+00:00" in log_content or "Z" in log_content or "2026" in log_content


# ---------------------------------------------------------------------------
# _global_archivist_job scheduler integration tests
# ---------------------------------------------------------------------------

class TestGlobalArchivistJob:
    """Tests for the _global_archivist_job scheduler entry point."""

    @pytest.fixture(autouse=True)
    def _mock_heavy_deps(self):
        """Mock psycopg2 and apscheduler so scheduler.py can be imported without DB."""
        import sys
        mocks = {
            "psycopg2": MagicMock(),
            "apscheduler": MagicMock(),
            "apscheduler.schedulers": MagicMock(),
            "apscheduler.schedulers.asyncio": MagicMock(),
            "apscheduler.triggers": MagicMock(),
            "apscheduler.triggers.date": MagicMock(),
            "apscheduler.jobstores": MagicMock(),
            "apscheduler.jobstores.sqlalchemy": MagicMock(),
        }
        # Only inject mocks for modules not already loaded
        to_restore = {}
        for name, mock in mocks.items():
            if name not in sys.modules:
                sys.modules[name] = mock
                to_restore[name] = None
        # Ensure scheduler module is freshly importable
        sys.modules.pop("scheduler", None)
        yield
        for name in to_restore:
            sys.modules.pop(name, None)
        sys.modules.pop("scheduler", None)

    @pytest.mark.asyncio
    async def test_calls_archivist_run_when_leader(self):
        """When the scheduler is leader, archivist_run() must be called."""
        mock_sched = MagicMock()
        mock_sched.is_leader = True

        with patch.dict("sys.modules", {"mcp_server": MagicMock(scheduler=mock_sched)}), \
             patch("ghost.archivist.run") as mock_run:
            from scheduler import _global_archivist_job
            await _global_archivist_job("test-user")

        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_archivist_run_when_not_leader(self):
        """When the scheduler is not leader, archivist_run() must NOT be called."""
        mock_sched = MagicMock()
        mock_sched.is_leader = False

        with patch.dict("sys.modules", {"mcp_server": MagicMock(scheduler=mock_sched)}), \
             patch("ghost.archivist.run") as mock_run:
            from scheduler import _global_archivist_job
            await _global_archivist_job("test-user")

        mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_logs_error_on_exception(self):
        """Exceptions inside archivist_run must be caught and logged, not raised."""
        import sys
        mock_sched = MagicMock()
        mock_sched.is_leader = True

        with patch.dict("sys.modules", {"mcp_server": MagicMock(scheduler=mock_sched)}), \
             patch("ghost.archivist.run", side_effect=RuntimeError("boom")):
            from scheduler import _global_archivist_job
            import scheduler as sched_mod
            with patch.object(sched_mod, "logger") as mock_logger:
                # Must not raise
                await _global_archivist_job("test-user")
            mock_logger.error.assert_called_once()
            assert "boom" in mock_logger.error.call_args[0][0]
