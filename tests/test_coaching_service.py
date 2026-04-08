import pytest
from unittest.mock import patch, MagicMock
from services.coaching_service import CoachingService, InsightType

@pytest.mark.asyncio
async def test_service_high_momentum_critical():
    # Setup Mocks (No global patching!)
    async def mock_context():
        return {
            "daily_walk_status": {"has_activity_today": True},
            "budget_governor": {"routing_recommendation": "helix"},
            "greek_backlog_boost": False,
            "greek_backlog_cards": 0
        }
    
    async def mock_goals():
        return [{"slug": "urgent", "title": "Urgent Goal", "derail_risk": "CRITICAL"}]
    
    async def mock_obsidian():
        return ""

    # Mock the language stats to have 0 reviews to avoid LEVER_PUSH override
    with patch("services.neon_sync_checker.NeonSyncChecker.get_language_stats") as mock_stats:
        mock_stats.return_value = {
            "arabic": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0},
            "greek": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0}
        }
        service = CoachingService(mock_context, mock_goals, mock_obsidian)
        insight = await service.generate_insight()
    
        assert insight.type == InsightType.MOMENTUM_PIVOT
        assert insight.momentum == "high"
        assert "Urgent Goal" in insight.message

@pytest.mark.asyncio
async def test_service_obsidian_context():
    async def mock_context():
        return {
            "daily_walk_status": {"has_activity_today": True},
            "budget_governor": {"routing_recommendation": "helix"},
            "greek_backlog_boost": False,
            "greek_backlog_cards": 0
        }
    
    async def mock_goals():
        return [] # No urgent goals
    
    async def mock_obsidian():
        return "Worked on Mecris architecture today"

    # Mock the language stats to have 0 reviews to avoid LEVER_PUSH override
    with patch("services.neon_sync_checker.NeonSyncChecker.get_language_stats") as mock_stats:
        mock_stats.return_value = {
            "arabic": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0},
            "greek": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0}
        }
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


@pytest.mark.asyncio
async def test_arabic_pressure_message_contains_arabic_script():
    """Issue #125: obnoxious Arabic reminders must include actual Arabic-script characters."""
    async def mock_context():
        return {"daily_walk_status": {"has_activity_today": False}, "greek_backlog_boost": False}

    async def mock_goals():
        return []

    async def mock_obsidian():
        return ""

    fake_lang_stats = {
        "arabic": {"current": 100, "tomorrow": 90, "multiplier": 2.0, "daily_completions": 5, "next_7_days": 0},
        "greek": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0, "next_7_days": 0},
    }

    mock_neon = MagicMock()
    mock_neon.get_language_stats.return_value = fake_lang_stats

    _ARABIC_RANGE = range(0x0600, 0x0700)

    with patch("services.neon_sync_checker.NeonSyncChecker", return_value=mock_neon):
        service = CoachingService(mock_context, mock_goals, mock_obsidian)
        # Run several times to cover all message variants (random.choice)
        messages_seen = set()
        for _ in range(20):
            insight = await service.generate_insight()
            messages_seen.add(insight.message)

    assert all(
        any(ord(ch) in _ARABIC_RANGE for ch in msg)
        for msg in messages_seen
    ), f"Not all Arabic pressure messages contain Arabic script. Messages: {messages_seen}"


@pytest.mark.asyncio
async def test_vacation_mode_walk_prompt_omits_dogs():
    """vacation_mode=True walk prompt must not mention 'Boris and Fiona' and must say 'movement'."""
    async def mock_context():
        return {"daily_walk_status": {"has_activity_today": False}, "vacation_mode": True, "greek_backlog_boost": False}

    async def mock_goals():
        return []

    async def mock_obsidian():
        return ""

    fake_lang_stats = {
        "arabic": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0, "next_7_days": 0},
        "greek": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0, "next_7_days": 0},
    }

    mock_neon = MagicMock()
    mock_neon.get_language_stats.return_value = fake_lang_stats

    with patch("services.neon_sync_checker.NeonSyncChecker", return_value=mock_neon):
        service = CoachingService(mock_context, mock_goals, mock_obsidian)
        insight = await service.generate_insight()

    assert insight.type == InsightType.WALK_PROMPT
    assert "Boris" not in insight.message, f"vacation_mode prompt must not mention dogs: {insight.message}"
    assert "Fiona" not in insight.message, f"vacation_mode prompt must not mention dogs: {insight.message}"
    assert "movement" in insight.message or "activity" in insight.message, (
        f"vacation_mode walk prompt should mention movement/activity: {insight.message}"
    )


@pytest.mark.asyncio
async def test_vacation_mode_urgency_alert_uses_activity_language():
    """vacation_mode=True urgency alert must say 'A quick personal activity', not 'A quick walk'."""
    async def mock_context():
        return {"daily_walk_status": {"has_activity_today": False}, "vacation_mode": True, "greek_backlog_boost": False}

    async def mock_goals():
        return [{"slug": "critical-goal", "title": "Critical Goal", "derail_risk": "CRITICAL"}]

    async def mock_obsidian():
        return ""

    fake_lang_stats = {
        "arabic": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0, "next_7_days": 0},
        "greek": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0, "next_7_days": 0},
    }

    mock_neon = MagicMock()
    mock_neon.get_language_stats.return_value = fake_lang_stats

    with patch("services.neon_sync_checker.NeonSyncChecker", return_value=mock_neon):
        service = CoachingService(mock_context, mock_goals, mock_obsidian)
        insight = await service.generate_insight()

    assert insight.type == InsightType.URGENCY_ALERT
    assert "A quick personal activity" in insight.message, (
        f"vacation_mode urgency alert should say 'A quick personal activity': {insight.message}"
    )
    assert "A quick walk" not in insight.message, (
        f"vacation_mode urgency alert must not say 'A quick walk': {insight.message}"
    )


@pytest.mark.asyncio
async def test_vacation_mode_high_momentum_pivot_uses_staying_active():
    """vacation_mode=True momentum pivot must say 'Nice work staying active!', not 'Great job on the walk!'."""
    async def mock_context():
        return {"daily_walk_status": {"has_activity_today": True}, "vacation_mode": True, "greek_backlog_boost": False}

    async def mock_goals():
        return [{"slug": "critical-goal", "title": "Critical Goal", "derail_risk": "CRITICAL"}]

    async def mock_obsidian():
        return ""

    fake_lang_stats = {
        "arabic": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0, "next_7_days": 0},
        "greek": {"current": 0, "tomorrow": 0, "multiplier": 1.0, "daily_completions": 0, "next_7_days": 0},
    }

    mock_neon = MagicMock()
    mock_neon.get_language_stats.return_value = fake_lang_stats

    with patch("services.neon_sync_checker.NeonSyncChecker", return_value=mock_neon):
        service = CoachingService(mock_context, mock_goals, mock_obsidian)
        insight = await service.generate_insight()

    assert insight.type == InsightType.MOMENTUM_PIVOT
    assert "Nice work staying active!" in insight.message, (
        f"vacation_mode momentum pivot should say 'Nice work staying active!': {insight.message}"
    )
    assert "Great job on the walk!" not in insight.message, (
        f"vacation_mode momentum pivot must not say 'Great job on the walk!': {insight.message}"
    )
