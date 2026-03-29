import pytest
from unittest.mock import patch, MagicMock
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


@pytest.mark.asyncio
async def test_arabic_lever_fires_with_lowercase_key():
    """Priority loop must use lowercase 'arabic' key to match get_language_stats() output."""
    async def mock_context():
        return {"daily_walk_status": {"has_activity_today": False}, "greek_backlog_boost": False}

    async def mock_goals():
        return []

    async def mock_obsidian():
        return ""

    fake_lang_stats = {
        "arabic": {"current": 100, "tomorrow": 90, "multiplier": 2.0, "daily_completions": 0, "next_7_days": 0},
        "greek": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0, "next_7_days": 0},
    }

    mock_neon = MagicMock()
    mock_neon.get_language_stats.return_value = fake_lang_stats

    with patch("services.neon_sync_checker.NeonSyncChecker", return_value=mock_neon):
        service = CoachingService(mock_context, mock_goals, mock_obsidian)
        insight = await service.generate_insight()

    assert insight.type == InsightType.LEVER_PUSH, (
        f"Expected LEVER_PUSH but got {insight.type}. "
        "Likely the priority loop used uppercase 'ARABIC' key and got empty stats."
    )
    assert insight.target_slug == "reviewstack"


@pytest.mark.asyncio
async def test_greek_lever_fires_with_lowercase_key():
    """Priority loop must use lowercase 'greek' key to match get_language_stats() output."""
    async def mock_context():
        return {"daily_walk_status": {"has_activity_today": False}, "greek_backlog_boost": False}

    async def mock_goals():
        return []

    async def mock_obsidian():
        return ""

    fake_lang_stats = {
        "arabic": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0, "next_7_days": 0},
        "greek": {"current": 100, "tomorrow": 90, "multiplier": 2.0, "daily_completions": 0, "next_7_days": 0},
    }

    mock_neon = MagicMock()
    mock_neon.get_language_stats.return_value = fake_lang_stats

    with patch("services.neon_sync_checker.NeonSyncChecker", return_value=mock_neon):
        service = CoachingService(mock_context, mock_goals, mock_obsidian)
        insight = await service.generate_insight()

    assert insight.type == InsightType.LEVER_PUSH, (
        f"Expected LEVER_PUSH but got {insight.type}. "
        "Likely the priority loop used uppercase 'GREEK' key and got empty stats."
    )
    assert insight.target_slug == "ellinika"


@pytest.mark.asyncio
async def test_high_momentum_greek_play_uses_lowercase_key():
    """_handle_high_momentum must use lowercase 'greek' key for play-mode check."""
    async def mock_context():
        return {"daily_walk_status": {"has_activity_today": True}, "greek_backlog_boost": False}

    async def mock_goals():
        return []

    async def mock_obsidian():
        return ""

    fake_lang_stats = {
        "greek": {"current": 30, "tomorrow": 0, "multiplier": 2.5, "daily_completions": 0, "next_7_days": 0},
    }

    mock_neon = MagicMock()
    mock_neon.get_language_stats.return_value = fake_lang_stats

    with patch("services.neon_sync_checker.NeonSyncChecker", return_value=mock_neon):
        service = CoachingService(mock_context, mock_goals, mock_obsidian)
        insight = await service.generate_insight()

    assert insight.type == InsightType.LEVER_PUSH, (
        f"Expected LEVER_PUSH (Greek play mode) but got {insight.type}. "
        "Likely _handle_high_momentum used uppercase 'GREEK' key and got empty stats."
    )
    assert insight.target_slug == "ellinika"
