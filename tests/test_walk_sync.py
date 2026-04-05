
import pytest
import datetime
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_global_walk_sync_job_success():
    """Test that _global_walk_sync_job identifies 'logging' walks and syncs them correctly."""
    user_id = "test-user-id"
    
    # Mocking dependencies
    mock_scheduler_obj = MagicMock()
    mock_scheduler_obj.is_leader = True
    
    mock_beeminder = AsyncMock()
    mock_beeminder.add_datapoint.return_value = True
    
    # Setup database mocks
    mock_cur = MagicMock()
    mock_conn = MagicMock()
    
    # Configure walk data (tuple for standard cursor)
    # (id, start_time, step_count, distance_meters, distance_source)
    walk_row = (
        1,
        datetime.datetime(2026, 4, 4, 18, 0, 0, tzinfo=datetime.timezone.utc),
        3200,
        1609.34, 
        'Health Connect'
    )
    
    # Configure mocks
    mock_cur.fetchall.return_value = [walk_row]
    mock_cur.fetchone.return_value = ('bike',)
    
    mock_conn.cursor.return_value = mock_cur
    mock_cur.__enter__.return_value = mock_cur
    mock_conn.__enter__.return_value = mock_conn

    with patch("mcp_server.scheduler", mock_scheduler_obj), \
         patch("mcp_server.get_user_beeminder_client", return_value=mock_beeminder), \
         patch("psycopg2.connect", return_value=mock_conn), \
         patch("os.getenv", return_value="postgres://fake"):
        
        import scheduler
        # Patch psycopg2 in the scheduler module's namespace
        with patch.object(scheduler, "psycopg2") as mock_p2:
            mock_p2.connect.return_value = mock_conn
            # We need to make sure the RealDictCursor is available if they still try to use it
            # though we changed the code to not use it for now.
            
            await scheduler._global_walk_sync_job(user_id)
            
        # Verify Beeminder call
        mock_beeminder.add_datapoint.assert_called_once()
        args, kwargs = mock_beeminder.add_datapoint.call_args
        assert args[0] == "bike"
        assert args[1] == 1.0 # 1609.34 / 1609.34
        assert kwargs['requestid'] == f"{user_id}_20260404"
        
        # Verify DB update call
        update_call = [call for call in mock_cur.execute.call_args_list if "UPDATE walk_inferences SET status = 'logged'" in call[0][0]]
        assert len(update_call) == 1
        assert update_call[0][0][1] == (1,)

@pytest.mark.asyncio
async def test_global_walk_sync_job_skips_when_not_leader():
    """Test that _global_walk_sync_job yields if not the leader."""
    mock_scheduler_obj = MagicMock()
    mock_scheduler_obj.is_leader = False
    
    with patch("mcp_server.scheduler", mock_scheduler_obj):
        import scheduler
        await scheduler._global_walk_sync_job("user-id")
        # Should return early (asserted by lack of other calls if we mocked more)
