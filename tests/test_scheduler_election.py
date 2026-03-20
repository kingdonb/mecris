import pytest
import datetime
import sys
from unittest.mock import patch, MagicMock

@pytest.fixture
def test_scheduler():
    """Provides a fresh instance of MecrisScheduler."""
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake"}):
        from scheduler import MecrisScheduler
        scheduler = MecrisScheduler()
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
    
    # Patch the psycopg2 module where it's used
    with patch("scheduler.psycopg2", mock_psycopg2):
        # The FIX: Mock get_job to return None so it thinks jobs don't exist yet
        test_scheduler.scheduler.get_job.return_value = None
        
        # Run the election attempt
        await test_scheduler._attempt_leadership()
        
        # It should have marked itself as leader
        assert test_scheduler.is_leader is True
        assert test_scheduler.scheduler.add_job.call_count == 3

@pytest.mark.asyncio
async def test_scheduler_election_yields_leader(test_scheduler):
    """Test that a node yields leadership if another node has claimed it."""
    
    mock_psycopg2 = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    # Setup chain
    mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    # Important: Set rowcount as an int
    mock_cur.rowcount = 0
    mock_cur.fetchone.return_value = ("other_process_id",)
    
    # Patch the psycopg2 module where it's used
    with patch("scheduler.psycopg2", mock_psycopg2):
        test_scheduler.process_id = "this_process_id"
        test_scheduler.is_leader = True
        # Ensure the mock scheduler is "running" so remove_job is called
        test_scheduler.scheduler.running = True
        
        await test_scheduler._attempt_leadership()
        
        # It should demote itself
        assert test_scheduler.is_leader is False
        # It should have removed its leader jobs (3 of them)
        assert test_scheduler.scheduler.remove_job.call_count == 3
