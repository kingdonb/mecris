import pytest
from unittest.mock import AsyncMock, MagicMock
from py_harness.mecris_harness import MecrisHarness

@pytest.mark.asyncio
async def test_harness_react_loop():
    # Mock LLM response with a tool call
    llm_client = AsyncMock()
    llm_client.chat.side_effect = [
        # First response: call a tool
        MagicMock(
            message=MagicMock(
                content=None,
                tool_calls=[MagicMock(function=MagicMock(name="get_narrator_context", arguments={}))]
            ),
            stop_reason="tool_use"
        ),
        # Second response: final answer
        MagicMock(
            message=MagicMock(content="I am Mecris.", tool_calls=None),
            stop_reason="stop"
        )
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
