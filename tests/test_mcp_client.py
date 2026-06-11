import pytest
from unittest.mock import AsyncMock, patch
from py_harness.mcp_client import MecrisMcpClient

@pytest.mark.asyncio
async def test_mcp_client_init():
    mock_read = AsyncMock()
    mock_write = AsyncMock()
    
    with patch("py_harness.mcp_client.stdio_client") as mock_stdio:
        # Create an async context manager mock
        cm = AsyncMock()
        cm.__aenter__.return_value = (mock_read, mock_write)
        mock_stdio.return_value = cm
        
        with patch("py_harness.mcp_client.ClientSession") as mock_session:
            session_cm = AsyncMock()
            session_cm.__aenter__.return_value = AsyncMock()
            mock_session.return_value = session_cm
            
            async with MecrisMcpClient() as client:
                assert client.session is not None
