import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.coaching_service import CoachingService, InsightType

@pytest.fixture
def mock_providers():
    context_provider = AsyncMock()
    goal_provider = AsyncMock()
    obsidian_provider = AsyncMock()
    
    # Default safe context
    context_provider.return_value = {
        "daily_walk_status": {"has_activity_today": False},
        "vacation_mode": False
    }
    goal_provider.return_value = []
    obsidian_provider.return_value = ""
    
    return context_provider, goal_provider, obsidian_provider

@pytest.mark.asyncio
async def test_arabic_pressure_lever_triggers(mock_providers):
    """Verify that Arabic 3x lever triggers high-pressure nagging."""
    ctx, goals, obs = mock_providers
    service = CoachingService(ctx, goals, obs)
    
    # Mock language stats in Neon
    mock_stats = {
        "ARABIC": {"current": 150, "multiplier": 3.0},
        "GREEK": {"current": 100, "multiplier": 1.0}
    }
    
    with patch("services.neon_sync_checker.NeonSyncChecker.get_language_stats", return_value=mock_stats):
        insight = await service.generate_insight()
        
        assert insight.type == InsightType.LEVER_PUSH
        assert "Arabic" in insight.message
        # Check for either "reviews" or "Debt"
        assert any(word in insight.message for word in ["reviews", "Debt"])
        assert insight.momentum == "low"

@pytest.mark.asyncio
async def test_greek_backlog_booster_triggers(mock_providers):
    """Verify that Greek 2x lever triggers PLAY encouragement when momentum is high."""
    ctx, goals, obs = mock_providers
    
    # Set high momentum (walk completed)
    ctx.return_value = {
        "daily_walk_status": {"has_activity_today": True},
        "vacation_mode": False
    }
    
    service = CoachingService(ctx, goals, obs)
    
    # Arabic is safe (1x), Greek is too low (< 50) with 2x lever
    mock_stats = {
        "ARABIC": {"current": 0, "multiplier": 1.0},
        "GREEK": {"current": 10, "multiplier": 2.0}
    }
    
    with patch("services.neon_sync_checker.NeonSyncChecker.get_language_stats", return_value=mock_stats):
        insight = await service.generate_insight()
        
        assert insight.type == InsightType.LEVER_PUSH
        assert "Greek" in insight.message
        assert "PLAY" in insight.message
        assert insight.momentum == "high"

@pytest.mark.asyncio
async def test_fallback_to_walk_prompt(mock_providers):
    """Verify fallback to walk prompt when no lever triggers match."""
    ctx, goals, obs = mock_providers
    service = CoachingService(ctx, goals, obs)
    
    # Multpliers are low, no activity
    mock_stats = {
        "ARABIC": {"current": 0, "multiplier": 1.0},
        "GREEK": {"current": 100, "multiplier": 1.0}
    }
    
    with patch("services.neon_sync_checker.NeonSyncChecker.get_language_stats", return_value=mock_stats):
        insight = await service.generate_insight()
        
        assert insight.type == InsightType.WALK_PROMPT
        assert "Boris and Fiona" in insight.message
