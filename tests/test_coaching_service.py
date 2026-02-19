import pytest
from services.coaching_service import CoachingService, InsightType

@pytest.mark.asyncio
async def test_service_high_momentum_critical():
    # Setup Mocks (No global patching!)
    async def mock_context():
        return {"daily_walk_status": {"has_activity_today": True}}
    
    async def mock_goals():
        return [{"slug": "urgent", "title": "Urgent Goal", "derail_risk": "CRITICAL"}]
    
    async def mock_obsidian():
        return ""

    service = CoachingService(mock_context, mock_goals, mock_obsidian)
    insight = await service.generate_insight()
    
    assert insight.type == InsightType.MOMENTUM_PIVOT
    assert insight.momentum == "high"
    assert "Urgent Goal" in insight.message

@pytest.mark.asyncio
async def test_service_obsidian_context():
    async def mock_context():
        return {"daily_walk_status": {"has_activity_today": True}}
    
    async def mock_goals():
        return [] # No urgent goals
    
    async def mock_obsidian():
        return "Worked on Mecris architecture today"

    service = CoachingService(mock_context, mock_goals, mock_obsidian)
    insight = await service.generate_insight()
    
    assert insight.type == InsightType.OBSIDIAN_PIVOT
    assert "Mecris" in insight.message
