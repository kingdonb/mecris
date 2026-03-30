import pytest
import datetime
from unittest.mock import patch, MagicMock
import asyncio

from services.reminder_service import ReminderService

# A helper to create async mock providers
def make_async_mock(return_value):
    async def mock_coro(*args, **kwargs):
        return return_value
    return mock_coro

@pytest.mark.asyncio
async def test_reminder_service_no_action_needed_morning():
    """Test that it stays quiet in the morning (10 AM) even if you haven't walked."""
    
    mock_context = {
        "daily_walk_status": {"has_activity_today": False},
        "beeminder_alerts": [],
        "goal_runway": []
    }
    mock_insight = {"momentum": "low", "message": "Get moving!"}
    
    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight))
    
    # Mock time to 10:00 AM
    class MockMorning(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 20, 10, 0, 0)
            
    with patch('services.reminder_service.datetime', MockMorning):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is False
        assert result["reason"] == "No conditions met for reminder"

@pytest.mark.asyncio
async def test_reminder_service_walk_reminder_afternoon():
    """Test that it fires a walk reminder between 2 PM and 5 PM if no walk is detected."""
    
    mock_context = {
        "daily_walk_status": {"has_activity_today": False},
        "beeminder_alerts": [],
        "goal_runway": []
    }
    mock_insight = {"momentum": "low", "message": "Get moving!"}
    
    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight))
    
    # Mock time to 3:00 PM (15:00)
    class MockAfternoon(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 20, 15, 0, 0)
            
    with patch('services.reminder_service.datetime', MockAfternoon):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "walk_reminder"
        assert result["template_sid"] == rs.walk_template_sid
        assert result["variables"]["1"] == "Daily Walk"
        assert result["variables"]["2"] == "NOT FOUND"

@pytest.mark.asyncio
async def test_reminder_service_no_walk_reminder_if_already_walked():
    """Test that it stays quiet in the afternoon if you HAVE walked."""
    
    mock_context = {
        "daily_walk_status": {"has_activity_today": True}, # User walked!
        "beeminder_alerts": [],
        "goal_runway": []
    }
    mock_insight = {"momentum": "high", "message": "Great job!"}
    
    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight))
    
    # Mock time to 3:00 PM (15:00)
    class MockAfternoon(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 20, 15, 0, 0)
            
    with patch('services.reminder_service.datetime', MockAfternoon):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is False

@pytest.mark.asyncio
async def test_reminder_service_momentum_coaching_late_afternoon():
    """Test that it pivots to momentum coaching late in the day if you crushed it."""
    
    mock_context = {
        "daily_walk_status": {"has_activity_today": True}, # User walked!
        "beeminder_alerts": [],
        "goal_runway": []
    }
    mock_insight = {"momentum": "high", "message": "You're on fire today."}
    
    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight))
    
    # Mock time to 4:30 PM (16:30)
    class MockLateAfternoon(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 20, 16, 30, 0)
            
    with patch('services.reminder_service.datetime', MockLateAfternoon):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "momentum_coaching"
        assert result["use_template"] is False
        assert result["message"] == "You're on fire today."

@pytest.mark.asyncio
async def test_reminder_service_beeminder_emergency_overrides_time():
    """Test that a CRITICAL non-Arabic Beeminder goal triggers a generic alert."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "weight", "title": "Weight Goal", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Emergency!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight))

    # Mock time to 8:00 AM (Outside walk window)
    class MockMorning(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 20, 8, 0, 0)

    with patch('services.reminder_service.datetime', MockMorning):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "beeminder_emergency"
        assert result["template_sid"] == rs.urgency_template_sid
        assert result["variables"]["1"] == "Weight Goal"
        assert result["variables"]["2"] == "0 days"


@pytest.mark.asyncio
async def test_arabic_review_reminder_fires_for_critical_reviewstack():
    """Test that a CRITICAL reviewstack goal triggers an arabic_review_reminder (obnoxious)."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "reviewstack", "title": "Arabic Reviews", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Do your Arabic!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight))

    class MockMorning(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 30, 9, 0, 0)

    with patch('services.reminder_service.datetime', MockMorning):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "arabic_review_reminder"
        assert result["template_sid"] == rs.urgency_template_sid
        assert "Arabic" in result["variables"]["1"] or "reviewstack" in result["variables"]["1"].lower()
        assert result["variables"]["2"] == "0 days"


@pytest.mark.asyncio
async def test_arabic_review_reminder_has_shorter_cooldown():
    """Test that arabic_review_reminder respects a 2h cooldown (shorter than 4h generic)."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "reviewstack", "title": "Arabic Reviews", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Do your Arabic!"}

    # Sent 1.5h ago — within 2h cooldown. Use a fixed timestamp so the mocked 'now' diff is predictable.
    MOCKED_NOW = datetime.datetime(2026, 3, 30, 11, 0, 0)
    SENT_AT = MOCKED_NOW - datetime.timedelta(hours=1.5)

    async def mock_last_sent(msg_type, user_id=None):
        if msg_type == "arabic_review_reminder":
            return SENT_AT
        return None

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight), log_provider=mock_last_sent)

    class MockNow(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return MOCKED_NOW

    with patch('services.reminder_service.datetime', MockNow):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is False
        assert "cooldown" in result.get("reason", "").lower()


@pytest.mark.asyncio
async def test_arabic_review_reminder_fires_after_2h_cooldown():
    """Test that arabic_review_reminder fires again after 2h has elapsed."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "reviewstack", "title": "Arabic Reviews", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Do your Arabic!"}

    # Last sent 2.5h ago — cooldown has elapsed. Fixed timestamps.
    MOCKED_NOW = datetime.datetime(2026, 3, 30, 13, 0, 0)
    SENT_AT = MOCKED_NOW - datetime.timedelta(hours=2.5)

    async def mock_last_sent(msg_type, user_id=None):
        if msg_type == "arabic_review_reminder":
            return SENT_AT
        return None

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight), log_provider=mock_last_sent)

    class MockNow(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return MOCKED_NOW

    with patch('services.reminder_service.datetime', MockNow):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "arabic_review_reminder"
