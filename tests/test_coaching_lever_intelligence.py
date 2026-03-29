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
async def test_arabic_pressure_neural_behind(mock_providers):
    """Verify nagging triggers when pace is behind target."""
    ctx, goals, obs = mock_providers
    service = CoachingService(ctx, goals, obs)
    
    # Arabic 3x lever (Brisk), debt 2400, tomorrow 10. 
    # Target should be approx 250 (2400/10 + 10)
    mock_stats = {
        "arabic": {"current": 2400, "tomorrow": 10, "multiplier": 3.0, "daily_completions": 50},
        "greek": {"current": 100, "multiplier": 1.0}
    }
    
    with patch("services.neon_sync_checker.NeonSyncChecker.get_language_stats", return_value=mock_stats):
        insight = await service.generate_insight()

        assert insight.type == InsightType.LEVER_PUSH
        assert "50/250" in insight.message
        assert "50/" in insight.message # Shows progress
        assert insight.momentum == "low"

@pytest.mark.asyncio
async def test_arabic_laminar_suppresses_nag(mock_providers):
    """Verify nagging stops when pace hits target (Laminar)."""
    ctx, goals, obs = mock_providers
    service = CoachingService(ctx, goals, obs)
    
    # Arabic 3x lever, target approx 250, done 300.
    mock_stats = {
        "arabic": {"current": 2400, "tomorrow": 10, "multiplier": 3.0, "daily_completions": 300},
        "greek": {"current": 100, "multiplier": 1.0}
    }
    
    with patch("services.neon_sync_checker.NeonSyncChecker.get_language_stats", return_value=mock_stats):
        insight = await service.generate_insight()
        
        # Should NOT be a LEVER_PUSH nag
        assert insight.type != InsightType.LEVER_PUSH
        # Should fallback to walk prompt
        assert insight.type == InsightType.WALK_PROMPT

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
        "arabic": {"current": 0, "multiplier": 1.0},
        "greek": {"current": 10, "multiplier": 2.0}
    }
    
    with patch("services.neon_sync_checker.NeonSyncChecker.get_language_stats", return_value=mock_stats):
        insight = await service.generate_insight()
        
        assert insight.type == InsightType.LEVER_PUSH
        assert "Greek" in insight.message
        assert "PLAY" in insight.message
        assert insight.momentum == "high"
