import pytest
import sys
import os
from py_harness.mcp_client import MecrisMcpClient

@pytest.mark.asyncio
async def test_mcp_real_server_narrator_context():
    """
    Integration test: Verify that we can actually call get_narrator_context
    on the real local server script.
    """
    # Ensure we are in the project root
    server_script = "mcp_server.py"
    if not os.path.exists(server_script):
        pytest.skip("mcp_server.py not found in current directory")

    async with MecrisMcpClient(server_script=server_script) as client:
        # Call the tool
        result = await client.call_tool("get_narrator_context", {})
        
        # Verify the result structure (CallToolResult)
        assert hasattr(result, "content")
        assert len(result.content) > 0
        
        # Check for typical narrator context keys in the text output
        text_content = result.content[0].text
        assert "summary" in text_content.lower() or "goals" in text_content.lower()
        print(f"\nReal MCP output: {text_content[:100]}...")
