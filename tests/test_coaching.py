import pytest
from unittest.mock import patch
from mcp_server import get_coaching_insight

@pytest.mark.asyncio
async def test_get_coaching_insight_high_momentum_critical():
    # Mock context where walk is done and there's a critical goal
    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
    }
    mock_goals = [
        {"slug": "urgent-goal", "title": "Urgent Goal", "derail_risk": "CRITICAL"}
    ]
    
    with patch("mcp_server.get_narrator_context", return_value=mock_context), \
         patch("mcp_server.get_cached_beeminder_goals", return_value=mock_goals):
        
        insight = await get_coaching_insight()
        
        assert insight["type"] == "momentum_pivot"
        assert insight["momentum"] == "high"
        assert "Great job on the walk" in insight["message"]
        assert "Urgent Goal" in insight["message"]
        assert insight["target_slug"] == "urgent-goal"

@pytest.mark.asyncio
async def test_get_coaching_insight_no_walk_critical():
    # Mock context where walk is NOT done and there's a critical goal
    mock_context = {
        "daily_walk_status": {"has_activity_today": False},
    }
    mock_goals = [
        {"slug": "urgent-goal", "title": "Urgent Goal", "derail_risk": "CRITICAL"}
    ]
    
    with patch("mcp_server.get_narrator_context", return_value=mock_context), \
         patch("mcp_server.get_cached_beeminder_goals", return_value=mock_goals):
        
        insight = await get_coaching_insight()
        
        assert insight["type"] == "urgency_alert"
        assert insight["momentum"] == "low"
        assert "Urgent Goal" in insight["message"]
        assert "Boris and Fiona" in insight["message"]

@pytest.mark.asyncio
async def test_get_coaching_insight_neutral():
    # Mock context where walk is NOT done and goals are safe
    mock_context = {
        "daily_walk_status": {"has_activity_today": False},
    }
    mock_goals = [
        {"slug": "safe-goal", "title": "Safe Goal", "derail_risk": "SAFE"}
    ]
    
    with patch("mcp_server.get_narrator_context", return_value=mock_context), \
         patch("mcp_server.get_cached_beeminder_goals", return_value=mock_goals):
        
        insight = await get_coaching_insight()
        
        assert insight["type"] == "walk_prompt"
        assert insight["momentum"] == "neutral"
        assert "ready when you are" in insight["message"]

@pytest.mark.asyncio
async def test_get_coaching_insight_obsidian_context():
    # Mock context with Obsidian activity
    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
    }
    # We'll need to mock the obsidian client call in mcp_server
    mock_goals = []
    mock_obsidian_activity = "Worked on Mecris architecture"
    
    with patch("mcp_server.get_narrator_context", return_value=mock_context), \
         patch("mcp_server.get_cached_beeminder_goals", return_value=mock_goals), \
         patch("mcp_server.obsidian_client.get_daily_note", return_value=mock_obsidian_activity):
        
        insight = await get_coaching_insight()
        
        assert "Mecris" in insight["message"]
        assert insight["type"] == "obsidian_pivot"
