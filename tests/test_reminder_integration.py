import pytest
from unittest.mock import patch, MagicMock
import asyncio

@pytest.mark.asyncio
async def test_trigger_reminder_check_integration():
    """Test that trigger_reminder_check correctly coordinates service and messaging."""
    
    # Mock the dependencies
    mock_reminder_data = {
        "should_send": True,
        "type": "test_reminder",
        "message": "Integrity check"
    }
    
    with patch("mcp_server.reminder_service.check_reminder_needed", return_value=mock_reminder_data) as mock_check:
        with patch("mcp_server.send_reminder_message", return_value={"sent": True}) as mock_send:
            from mcp_server import trigger_reminder_check
            
            result = await trigger_reminder_check()
            
            assert result["triggered"] is True
            mock_check.assert_called_once()
            mock_send.assert_called_once()
            # check the first arg is mock_reminder_data
            assert mock_send.call_args[0][0] == mock_reminder_data

@pytest.mark.asyncio
async def test_trigger_reminder_check_skips_when_not_needed():
    """Test that trigger_reminder_check stays quiet when no reminder is needed."""
    
    mock_reminder_data = {"should_send": False, "reason": "Quiet time"}
    
    with patch("mcp_server.reminder_service.check_reminder_needed", return_value=mock_reminder_data):
        with patch("mcp_server.send_reminder_message") as mock_send:
            from mcp_server import trigger_reminder_check
            
            result = await trigger_reminder_check()
            
            assert result["triggered"] is False
            assert result["reason"] == "Quiet time"
            mock_send.assert_not_called()
