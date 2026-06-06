import pytest
from unittest.mock import AsyncMock
from py_harness.mecris_harness import MecrisHarness

@pytest.mark.asyncio
async def test_harness_react_loop():
    # Mock LLM response with a tool call
    llm_client = AsyncMock()
    llm_client.chat.side_effect = [
        # First response: call a tool
        {
            "message": {
                "content": None,
                "tool_calls": [{"function": {"name": "get_narrator_context", "arguments": {}}}]
            },
            "done": False
        },
        # Second response: final answer
        {
            "message": {"content": "I am Mecris.", "tool_calls": None},
            "done": True
        }
    ]

    # Mock MCP client
    mcp_client = AsyncMock()
    mcp_client.call_tool.return_value = '{"summary": "Everything is fine"}'

    harness = MecrisHarness(llm_client=llm_client, mcp_client=mcp_client)
    
    messages = [{"role": "user", "content": "Status report"}]
    final_response = await harness.run_loop(messages)

    assert final_response == "I am Mecris."
    assert mcp_client.call_tool.called
    assert llm_client.chat.call_count == 2
