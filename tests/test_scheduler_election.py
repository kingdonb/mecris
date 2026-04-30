import pytest
import datetime
import sys
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.fixture
def test_scheduler():
    """Provides a fresh instance of MecrisScheduler."""
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user", "MECRIS_MODE": "standalone"}):
        from scheduler import MecrisScheduler
        scheduler = MecrisScheduler(user_id="test-user")
        scheduler.scheduler = MagicMock()
        yield scheduler

@pytest.mark.asyncio
async def test_scheduler_election_claims_leader(test_scheduler):
    """Test that a node successfully claims leadership if the table is empty or heartbeat is stale."""
    
    mock_psycopg2 = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    # Setup chain
    mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    # Important: Set rowcount as an int
    mock_cur.rowcount = 1
    
    # Patch the psycopg2 module and start/stop jobs
    with patch("scheduler.psycopg2", mock_psycopg2), \
         patch.object(test_scheduler, "_start_leader_jobs", AsyncMock()) as mock_start:
        
        test_scheduler.neon_url = "postgres://fake"
        await test_scheduler._attempt_leadership()

        # It should have marked itself as leader
        assert test_scheduler.is_leader is True
        mock_start.assert_called_once()

@pytest.mark.asyncio
async def test_scheduler_election_yields_leader(test_scheduler):
    """Test that a node yields leadership if another node has claimed it."""

    mock_psycopg2 = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()

    # Setup chain
    mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Rowcount 0 means we didn't update (claim) the row
    mock_cur.rowcount = 0
    mock_cur.fetchone.return_value = ("other_process_id", datetime.datetime.now())

    with patch("scheduler.psycopg2", mock_psycopg2), \
         patch.object(test_scheduler, "_stop_leader_jobs", MagicMock()) as mock_stop:
        
        test_scheduler.neon_url = "postgres://fake"
        test_scheduler.process_id = "this_process_id"
        test_scheduler.is_leader = True
        
        await test_scheduler._attempt_leadership()

        # It should demote itself
        assert test_scheduler.is_leader is False
        mock_stop.assert_called_once()


# ---------------------------------------------------------------------------
# _write_obs_status — last_error write path (yebyen/mecris#283)
# ---------------------------------------------------------------------------

class TestWriteObsStatus:
    def test_write_obs_status_with_error_writes_last_error(self, test_scheduler):
        """When error=str is passed, _write_obs_status includes it in the UPDATE."""
        mock_cur = MagicMock()
        test_scheduler._has_obs_columns = True
        test_scheduler.user_id = "test-user"
        test_scheduler.process_id = "pid-111"

        test_scheduler._write_obs_status(mock_cur, "Lost leadership", "standby", error="preempted by other_pid")

        # Find the UPDATE call among the execute calls
        execute_calls = [str(c) for c in mock_cur.execute.call_args_list]
        update_call = next((c for c in mock_cur.execute.call_args_list
                            if "UPDATE" in str(c)), None)
        assert update_call is not None, "Expected an UPDATE execute call"
        args = update_call.args[1]  # (last_status, intent, error, user_id, process_id)
        assert args[2] == "preempted by other_pid", f"last_error not written correctly, got: {args[2]}"

    def test_write_obs_status_without_error_writes_null(self, test_scheduler):
        """When error is omitted (default None), _write_obs_status writes NULL for last_error."""
        mock_cur = MagicMock()
        test_scheduler._has_obs_columns = True
        test_scheduler.user_id = "test-user"
        test_scheduler.process_id = "pid-222"

        test_scheduler._write_obs_status(mock_cur, "Heartbeat active", "maintain leadership")

        update_call = next((c for c in mock_cur.execute.call_args_list
                            if "UPDATE" in str(c)), None)
        assert update_call is not None, "Expected an UPDATE execute call"
        args = update_call.args[1]
        assert args[2] is None, f"last_error should be None when not specified, got: {args[2]}"

    def test_write_obs_status_skipped_when_columns_absent(self, test_scheduler):
        """When _has_obs_columns is False, _write_obs_status returns immediately without DB calls."""
        mock_cur = MagicMock()
        test_scheduler._has_obs_columns = False

        test_scheduler._write_obs_status(mock_cur, "any", "any", error="any")

        mock_cur.execute.assert_not_called()

    def test_heartbeat_maintenance_no_name_error(self, test_scheduler):
        """Regression test: heartbeat-maintenance branch must NOT raise NameError.

        This exercises the is_leader=True + row[0]==process_id path (scheduler.py:330-335).
        The `attempt` variable referenced there was never defined — yebyen/mecris#315.
        """
        mock_psycopg2 = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        # rowcount=0 → UPDATE didn't (re-)claim the row
        mock_cur.rowcount = 0
        # fetchone returns our own process_id → we ARE still leader in DB
        mock_cur.fetchone.return_value = ("this_process_id", datetime.datetime.now())
        test_scheduler._has_obs_columns = True

        with patch("scheduler.psycopg2", mock_psycopg2), \
             patch.object(test_scheduler, "_start_leader_jobs", AsyncMock()):
            test_scheduler.neon_url = "postgres://fake"
            test_scheduler.process_id = "this_process_id"
            test_scheduler.is_leader = True

            # Must not raise NameError
            import asyncio
            asyncio.get_event_loop().run_until_complete(test_scheduler._attempt_leadership())

        # Still leader — no demotion
        assert test_scheduler.is_leader is True

    def test_lost_leadership_path_writes_error(self, test_scheduler):
        """When demoted, _attempt_leadership calls _write_obs_status with a non-None error."""
        mock_psycopg2 = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.rowcount = 0
        mock_cur.fetchone.return_value = ("other_process_id", datetime.datetime.now())
        test_scheduler._has_obs_columns = True

        with patch("scheduler.psycopg2", mock_psycopg2), \
             patch.object(test_scheduler, "_stop_leader_jobs", MagicMock()):
            test_scheduler.neon_url = "postgres://fake"
            test_scheduler.process_id = "this_process_id"
            test_scheduler.is_leader = True

            import asyncio
            asyncio.get_event_loop().run_until_complete(test_scheduler._attempt_leadership())

        # Find the UPDATE obs call that includes "Lost leadership"
        update_calls = [c for c in mock_cur.execute.call_args_list if "UPDATE" in str(c)]
        lost_call = next((c for c in update_calls if "Lost leadership" in str(c)), None)
        assert lost_call is not None, "Expected _write_obs_status call for lost leadership"
        args = lost_call.args[1]
        assert args[2] is not None, "error arg should be non-None on lost leadership"
        assert "other_process_id" in args[2]
