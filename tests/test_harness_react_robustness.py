import pytest
from unittest.mock import AsyncMock, MagicMock
from py_harness.mecris_harness import MecrisHarness

@pytest.mark.asyncio
async def test_react_fallback_json_mixed_text():
    # Test that a JSON tool call mixed with text is correctly extracted and executed
    mock_llm = AsyncMock()
    mock_mcp = AsyncMock()
    
    # Mock LLM returns conversational text + JSON block
    mock_llm.use_native_tools = False
    mock_llm.model = "qwen2:1.5b"
    
    # First turn: returns tool call
    # Second turn: returns final conversational text
    mock_llm.chat.side_effect = [
        {
            "message": {
                "role": "assistant",
                "content": 'I need info first.\n\n{"tool": "get_narrator_context", "arguments": {}}'
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "All good!"
            }
        }
    ]
    
    # Mock MCP tool call response
    mock_call_result = MagicMock()
    mock_text_content = MagicMock()
    mock_text_content.text = '{"summary": "Goals are safe"}'
    mock_call_result.content = [mock_text_content]
    mock_mcp.call_tool.return_value = mock_call_result
    
    harness = MecrisHarness(mock_llm, mock_mcp)
    messages = []
    tools = [{"name": "get_narrator_context", "description": "Get context"}]
    
    response = await harness.run_loop(messages, tools=tools)
    
    assert response == "All good!"
    # Verify MCP tool was called once
    mock_mcp.call_tool.assert_called_once_with("get_narrator_context", {})

@pytest.mark.asyncio
async def test_react_fallback_bare_word_capitalized():
    # Test that "Get_narrator_context" (capitalized, bare text) triggers the tool call
    mock_llm = AsyncMock()
    mock_mcp = AsyncMock()
    mock_llm.use_native_tools = False
    mock_llm.model = "qwen2:1.5b"
    
    mock_llm.chat.side_effect = [
        {
            "message": {
                "role": "assistant",
                "content": "Let me see. Get_narrator_context"
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "Finished check."
            }
        }
    ]
    
    mock_call_result = MagicMock()
    mock_text_content = MagicMock()
    mock_text_content.text = "{}"
    mock_call_result.content = [mock_text_content]
    mock_mcp.call_tool.return_value = mock_call_result
    
    harness = MecrisHarness(mock_llm, mock_mcp)
    messages = []
    tools = [{"name": "get_narrator_context"}]
    
    response = await harness.run_loop(messages, tools=tools)
    
    assert response == "Finished check."
    mock_mcp.call_tool.assert_called_once_with("get_narrator_context", {})

@pytest.mark.asyncio
async def test_react_fallback_chinese_context():
    # Test that Chinese tool trigger words like "使用 get_narrator_context" still match
    mock_llm = AsyncMock()
    mock_mcp = AsyncMock()
    mock_llm.use_native_tools = False
    mock_llm.model = "qwen2:1.5b"
    
    mock_llm.chat.side_effect = [
        {
            "message": {
                "role": "assistant",
                "content": "好的，我来 激将 使用 get_narrator_context"
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "任务完成"
            }
        }
    ]
    
    mock_call_result = MagicMock()
    mock_text_content = MagicMock()
    mock_text_content.text = "{}"
    mock_call_result.content = [mock_text_content]
    mock_mcp.call_tool.return_value = mock_call_result
    
    harness = MecrisHarness(mock_llm, mock_mcp)
    messages = []
    tools = [{"name": "get_narrator_context"}]
    
    response = await harness.run_loop(messages, tools=tools)
    
    assert response == "任务完成"
    mock_mcp.call_tool.assert_called_once_with("get_narrator_context", {})
