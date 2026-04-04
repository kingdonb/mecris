import pytest
import sys
from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_scheduler_to_mcp_circular_import_safety():
    """
    Verify that scheduler.py can safely import from mcp_server.py 
    inside its background jobs without exploding.
    """
    
    # We need to mock mcp_server because it tries to start many things on import
    mock_mcp_server = MagicMock()
    mock_mcp_server.scheduler = MagicMock()
    mock_mcp_server.scheduler.is_leader = True
    
    # Mock the trigger function
    mock_trigger = MagicMock()
    async def async_trigger(user_id=None, **kwargs):
        mock_trigger(user_id)
        return {"triggered": True}
    mock_mcp_server.trigger_reminder_check = async_trigger    
    with patch.dict("sys.modules", {"mcp_server": mock_mcp_server}):
        from scheduler import _global_reminder_job

        # This shouldn't raise ImportError or any other exception
        await _global_reminder_job("test_func", "test_user")        
        # Verify the trigger was actually called
        mock_trigger.assert_called_once()
