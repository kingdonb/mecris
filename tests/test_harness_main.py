import pytest
import sys
from unittest.mock import AsyncMock, patch
from py_harness.main import main

@pytest.mark.asyncio
async def test_main_loop_exit():
    # Test that entering "exit" immediately quits the loop without chatting
    with patch("py_harness.main.MecrisMcpClient") as mock_mcp, \
         patch("py_harness.main.OllamaClient") as mock_ollama, \
         patch("py_harness.main.MecrisHarness") as mock_harness, \
         patch("builtins.input", return_value="exit"):
        
        # Setup mocks to avoid real I/O
        mock_mcp_instance = AsyncMock()
        mock_mcp_instance.list_tools.return_value = {"tools": [{"name": "get_narrator_context"}]}
        mock_mcp.return_value.__aenter__.return_value = mock_mcp_instance
        
        mock_harness_instance = AsyncMock()
        mock_harness_instance.run_loop.return_value = "Goodbye!"
        mock_harness.return_value = mock_harness_instance

        # Should not raise exception
        await main()

        # Since user inputs 'exit' initially, it should not call run_loop
        assert not mock_harness_instance.run_loop.called
