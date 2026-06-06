import pytest
from py_harness.mcp_client import filter_core_tools

def test_filter_core_tools():
    all_tools = [
        {"name": "get_narrator_context", "description": "Core"},
        {"name": "get_daily_aggregate_status", "description": "Core"},
        {"name": "delete_user_data", "description": "Admin"},
        {"name": "record_usage_session", "description": "Rare"},
        {"name": "search_bookmarks", "description": "Core"}
    ]
    
    core_tools = filter_core_tools(all_tools)
    
    assert len(core_tools) == 1
    names = [t["name"] for t in core_tools]
    assert "get_narrator_context" in names
    assert "get_daily_aggregate_status" not in names
