import pytest
from unittest.mock import MagicMock, patch
from services.neon_sync_checker import NeonSyncChecker
from datetime import datetime, timezone
import zoneinfo

@pytest.fixture
def checker():
    with patch.dict('os.environ', {'NEON_DB_URL': 'postgres://fake'}):
        with patch('psycopg2.connect') as mock_connect:
            checker = NeonSyncChecker()
            yield checker

@pytest.mark.asyncio
async def test_has_walk_today_workout_bypass(checker):
    # Setup mock cursor to return 1 (walk found via Workouts source)
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (1,)
    mock_conn.cursor.return_value = mock_cur
    
    with patch('psycopg2.connect', return_value=mock_conn):
        # Even with 100 steps, it should return True because of the 'Workouts' SQL clause
        result = checker.has_walk_today(user_id="test", min_steps=2000)
        assert result is True
        
        # Verify the query includes the new conditions
        args, kwargs = mock_cur.execute.call_args
        query = args[0]
        assert "distance_source LIKE '%%Workouts%%'" in query
        assert "distance_meters AS FLOAT) >= 1609.34" in query

@pytest.mark.asyncio
async def test_has_walk_today_distance_bypass(checker):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (1,)
    mock_conn.cursor.return_value = mock_cur
    
    with patch('psycopg2.connect', return_value=mock_conn):
        # 1609.34m is 1.0 mile. Should count as a walk.
        result = checker.has_walk_today(user_id="test", min_steps=2000)
        assert result is True
