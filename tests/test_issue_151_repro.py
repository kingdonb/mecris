import pytest
from unittest.mock import patch, MagicMock
from services.coaching_service import CoachingService, InsightType

@pytest.mark.asyncio
async def test_repro_arabic_not_done_before_greek_play():
    """
    REPRODUCE ISSUE #151:
    If Arabic (reviewstack) is not 'done' according to the ReviewPump,
    it should be prioritized even if its multiplier is < 3.0,
    and before Greek 'PLAY' driver is recommended.
    """
    
    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "vacation_mode": False
    }
    
    # Arabic: current=100, tomorrow=10, multiplier=2.0 (Steady, 14 days)
    # Target = 10 + (100 / 14) = 17
    # daily_completions = 5 (NOT DONE)
    # Greek: current=10, multiplier=2.0 (SAFE, triggers PLAY in current logic)
    
    mock_lang_stats = {
        "ARABIC": {
            "current": 100,
            "tomorrow": 10,
            "multiplier": 2.0,
            "daily_completions": 5
        },
        "GREEK": {
            "current": 10,
            "multiplier": 2.0,
            "daily_completions": 0
        }
    }
    
    # Mock goals list (no critical goals to avoid interference)
    mock_goals = []
    
    # Define providers for the service
    async def mock_context_provider(): return mock_context
    async def mock_goal_provider(): return mock_goals
    async def mock_obsidian_provider(): return None

    service = CoachingService(
        context_provider=mock_context_provider,
        goal_provider=mock_goal_provider,
        obsidian_provider=mock_obsidian_provider
    )
    
    # Patch NeonSyncChecker.get_language_stats
    with patch("services.neon_sync_checker.NeonSyncChecker.get_language_stats", return_value=mock_lang_stats):
        insight = await service.generate_insight()
        
        # EXPECTATION: Arabic should be the target because it is NOT DONE.
        # ACTUAL (BUG): It will likely recommend Greek PLAY because Arabic multiplier < 3.0.
        
        assert insight.target_slug == "reviewstack", f"Expected Arabic priority, got {insight.target_slug} ({insight.message})"
        assert "Arabic" in insight.message
