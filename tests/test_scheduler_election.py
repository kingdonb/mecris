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
