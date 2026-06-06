import pytest
from unittest.mock import AsyncMock, patch
from py_harness.mcp_client import MecrisMcpClient

@pytest.mark.asyncio
async def test_mcp_client_init():
    with patch("mcp.client.stdio.stdio_client") as mock_stdio:
        mock_stdio.return_value.__aenter__.return_value = (AsyncMock(), AsyncMock())
        client = MecrisMcpClient()
        # In a real test we'd need more mocks for the session
        assert client is not None
