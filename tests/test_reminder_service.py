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
async def test_arabic_review_reminder_includes_cards_needed_when_velocity_provider_set():
    """Phase 2: variable '3' is populated with target_flow_rate when velocity_provider is present."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "reviewstack", "title": "Arabic Reviews", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Do your Arabic!"}
    mock_velocity = {"arabic": {"target_flow_rate": 42, "status": "cavitation", "unit": "cards"}}

    rs = ReminderService(
        make_async_mock(mock_context),
        make_async_mock(mock_insight),
        velocity_provider=make_async_mock(mock_velocity)
    )

    class MockNow(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 30, 9, 0, 0)

    with patch('services.reminder_service.datetime', MockNow):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "arabic_review_reminder"
        assert result["variables"].get("3") == "42"


@pytest.mark.asyncio
async def test_arabic_review_reminder_omits_variable3_without_velocity_provider():
    """Phase 2: when velocity_provider is absent, variable '3' is not set (graceful fallback)."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "reviewstack", "title": "Arabic Reviews", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Do your Arabic!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight))

    class MockNow(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 30, 9, 0, 0)

    with patch('services.reminder_service.datetime', MockNow):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "arabic_review_reminder"
        assert "3" not in result["variables"]


@pytest.mark.asyncio
async def test_arabic_review_escalation_fires_after_3_ignored_cycles():
    """Phase 3: arabic_review_escalation fires when skip_count >= 3 and 1h cooldown has elapsed."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "reviewstack", "title": "Arabic Reviews", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Do your Arabic!"}

    async def mock_skip_count(user_id=None):
        return 4  # ignored 4 consecutive cycles

    rs = ReminderService(
        make_async_mock(mock_context),
        make_async_mock(mock_insight),
        skip_count_provider=mock_skip_count
    )

    class MockNow(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 30, 9, 0, 0)

    with patch('services.reminder_service.datetime', MockNow):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "arabic_review_escalation"
        assert result["template_sid"] == rs.urgency_template_sid
        assert result["variables"]["3"] == "4"
        assert "Arabic" in result["variables"]["1"] or "reviewstack" in result["variables"]["1"].lower()


@pytest.mark.asyncio
async def test_arabic_review_escalation_resets_when_cards_done():
    """Phase 3: when skip_count == 0 (cards_today > 0), falls back to arabic_review_reminder, not escalation."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "reviewstack", "title": "Arabic Reviews", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Do your Arabic!"}

    async def mock_skip_count(user_id=None):
        return 0  # reset — user did their reviews

    rs = ReminderService(
        make_async_mock(mock_context),
        make_async_mock(mock_insight),
        skip_count_provider=mock_skip_count
    )

    class MockNow(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 30, 9, 0, 0)

    with patch('services.reminder_service.datetime', MockNow):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "arabic_review_reminder"  # base reminder, not escalation


@pytest.mark.asyncio
async def test_arabic_review_escalation_respects_1h_cooldown():
    """Phase 3: escalation is suppressed if it was sent within the last 1h."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "reviewstack", "title": "Arabic Reviews", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Do your Arabic!"}

    MOCKED_NOW = datetime.datetime(2026, 3, 30, 11, 0, 0)
    SENT_AT = MOCKED_NOW - datetime.timedelta(minutes=30)  # 30 min ago — within 1h cooldown

    async def mock_last_sent(msg_type, user_id=None):
        if msg_type == "arabic_review_escalation":
            return SENT_AT
        return None

    async def mock_skip_count(user_id=None):
        return 5

    rs = ReminderService(
        make_async_mock(mock_context),
        make_async_mock(mock_insight),
        log_provider=mock_last_sent,
        skip_count_provider=mock_skip_count
    )

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


# --- Nag Ladder Tier tests ---

@pytest.mark.asyncio
async def test_global_rate_limit_suppresses_reminders():
    """Nag Ladder: No matter the type, aggregate frequency is capped at 2x/hour."""
    MOCKED_NOW = datetime.datetime(2026, 3, 20, 15, 0, 0)
    SENT_AT = MOCKED_NOW - datetime.timedelta(minutes=15)  # Sent 15m ago

    async def mock_last_sent(msg_type, user_id=None):
        if msg_type is None: # Any message
            return SENT_AT
        return None

    rs = ReminderService(make_async_mock({}), make_async_mock({}), log_provider=mock_last_sent)

    class MockNow(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return MOCKED_NOW

    with patch('services.reminder_service.datetime', MockNow):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is False
        assert "Global rate limit" in result["reason"]


@pytest.mark.asyncio
async def test_walk_reminder_has_tier_1():
    """Nag Ladder: walk_reminder returns tier 1 (gentle WhatsApp template)."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": False},
        "beeminder_alerts": [],
        "goal_runway": []
    }
    mock_insight = {"momentum": "low", "message": "Get moving!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight))

    class MockAfternoon(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 20, 15, 0, 0)

    with patch('services.reminder_service.datetime', MockAfternoon):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "walk_reminder"
        assert result["tier"] == 1


@pytest.mark.asyncio
async def test_arabic_review_escalation_has_tier_2():
    """Nag Ladder: arabic_review_escalation returns tier 2 (escalated template)."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "reviewstack", "title": "Arabic Reviews", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Do your Arabic!"}

    async def mock_skip_count(user_id=None):
        return 4  # ignored 4 consecutive cycles → escalation

    rs = ReminderService(
        make_async_mock(mock_context),
        make_async_mock(mock_insight),
        skip_count_provider=mock_skip_count
    )

    class MockNow(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 30, 9, 0, 0)

    with patch('services.reminder_service.datetime', MockNow):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "arabic_review_escalation"
        assert result["tier"] == 2


@pytest.mark.asyncio
async def test_beeminder_emergency_tier_3_fires_for_sub_2h_runway():
    """Nag Ladder: tier 3 beeminder_emergency_tier3 fires when a CRITICAL goal has '1.5 hours' runway."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "weight", "title": "Weight Goal", "derail_risk": "CRITICAL", "runway": "1.5 hours"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Emergency!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight))

    class MockMorning(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 20, 8, 0, 0)

    with patch('services.reminder_service.datetime', MockMorning):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "beeminder_emergency_tier3"
        assert result["tier"] == 3
        assert "Weight Goal" in result["fallback_message"]
        assert result["use_template"] is False


@pytest.mark.asyncio
async def test_beeminder_emergency_tier_3_not_triggered_for_days_runway():
    """Nag Ladder: '0 days' runway does NOT trigger tier 3 — 'today' is not 'within 2 hours'."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "weight", "title": "Weight Goal", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Emergency!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight))

    class MockMorning(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 20, 8, 0, 0)

    with patch('services.reminder_service.datetime', MockMorning):
        result = await rs.check_reminder_needed()
        # Should get beeminder_emergency (tier 1), NOT sms_emergency (tier 3)
        assert result["should_send"] is True
        assert result["type"] == "beeminder_emergency"
        assert result["tier"] == 1


# --- Tier 2 time-based escalation tests (yebyen/mecris#59) ---

@pytest.mark.asyncio
async def test_tier1_beeminder_emergency_escalates_to_tier2_after_6h_idle():
    """Tier 2 escalation: beeminder_emergency promoted to tier 2 after 7h idle."""

    MOCKED_NOW = datetime.datetime(2026, 3, 20, 8, 0, 0)
    SENT_AT = MOCKED_NOW - datetime.timedelta(hours=7)

    async def mock_last_sent(msg_type, user_id=None):
        if msg_type == "beeminder_emergency":
            return SENT_AT
        return None

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "weight", "title": "Weight Goal", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Emergency!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight), log_provider=mock_last_sent)

    class MockMorning(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return MOCKED_NOW

    with patch('services.reminder_service.datetime', MockMorning):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "beeminder_emergency"
        assert result["tier"] == 2
        assert result.get("use_template") is False


@pytest.mark.asyncio
async def test_tier1_beeminder_emergency_stays_tier1_under_6h_idle():
    """Tier 2 escalation: beeminder_emergency stays tier 1 when last sent < 6h ago."""

    MOCKED_NOW = datetime.datetime(2026, 3, 20, 12, 0, 0)
    SENT_AT = MOCKED_NOW - datetime.timedelta(hours=5)  # within TIER2_IDLE_HOURS

    async def mock_last_sent(msg_type, user_id=None):
        if msg_type == "beeminder_emergency":
            return SENT_AT
        return None

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "weight", "title": "Weight Goal", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Emergency!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight), log_provider=mock_last_sent)

    class MockNow(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return MOCKED_NOW

    with patch('services.reminder_service.datetime', MockNow):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "beeminder_emergency"
        assert result["tier"] == 1
        assert "use_template" not in result


@pytest.mark.asyncio
async def test_tier1_walk_reminder_escalates_to_tier2_after_6h_idle():
    """Tier 2 escalation: walk_reminder promoted to tier 2 when last sent 7h ago."""

    MOCKED_NOW = datetime.datetime(2026, 3, 20, 15, 0, 0)
    SENT_AT = MOCKED_NOW - datetime.timedelta(hours=7)

    async def mock_last_sent(msg_type, user_id=None):
        if msg_type == "walk_reminder":
            return SENT_AT
        return None

    mock_context = {
        "daily_walk_status": {"has_activity_today": False},
        "beeminder_alerts": [],
        "goal_runway": []
    }
    mock_insight = {"momentum": "low", "message": "Get moving!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight), log_provider=mock_last_sent)

    class MockAfternoon(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return MOCKED_NOW

    with patch('services.reminder_service.datetime', MockAfternoon):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "walk_reminder"
        assert result["tier"] == 2
        assert result.get("use_template") is False


@pytest.mark.asyncio
async def test_no_tier2_escalation_without_log_provider():
    """Tier 2 escalation: no escalation when log_provider is absent (no history)."""

    mock_context = {
        "daily_walk_status": {"has_activity_today": False},
        "beeminder_alerts": [],
        "goal_runway": []
    }
    mock_insight = {"momentum": "low", "message": "Get moving!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight))  # no log_provider

    class MockAfternoon(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls(2026, 3, 20, 15, 0, 0)

    with patch('services.reminder_service.datetime', MockAfternoon):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "walk_reminder"
        assert result["tier"] == 1  # no escalation without history
        assert "use_template" not in result


@pytest.mark.asyncio
async def test_tier2_escalation_resets_after_tier2_message_sent():
    """Tier 2 reset semantics (yebyen/mecris#61): implicit reset is sufficient.

    After a Tier 2 beeminder_emergency fires, the NEXT call (4h cooldown elapsed,
    goal still CRITICAL) returns Tier 1 — NOT Tier 2. The Tier 2 send itself resets
    hours_since_last("beeminder_emergency") to 0, so 4h later it is 4h < TIER2_IDLE_HOURS
    (6h) → no escalation. No explicit last_acknowledged field is needed.
    """
    MOCKED_NOW = datetime.datetime(2026, 3, 20, 12, 0, 0)
    # Simulates: Tier 2 was sent 4h ago (logged as "beeminder_emergency", same type)
    TIER2_SENT_AT = MOCKED_NOW - datetime.timedelta(hours=4)

    async def mock_last_sent(msg_type, user_id=None):
        if msg_type is None:  # global rate limit check (any type)
            return TIER2_SENT_AT
        if msg_type == "beeminder_emergency":
            return TIER2_SENT_AT
        return None

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "weight", "title": "Weight Goal", "derail_risk": "CRITICAL", "runway": "0 days"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Emergency!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight), log_provider=mock_last_sent)

    class MockNow(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return MOCKED_NOW

    with patch('services.reminder_service.datetime', MockNow):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "beeminder_emergency"
        assert result["tier"] == 1  # NOT Tier 2: 4h < TIER2_IDLE_HOURS (6h) → no escalation
        assert "use_template" not in result  # Tier 2 would set use_template=False


@pytest.mark.asyncio
async def test_tier2_walk_escalation_implicit_reset_when_user_walks():
    """Tier 2 reset semantics (yebyen/mecris#61): walk escalation cannot stick after activity.

    Even with a stale walk_reminder log entry (8h ago, which would trigger Tier 2 escalation),
    once has_activity_today=True the walk block is skipped entirely — _apply_tier2_escalation()
    is never called and should_send is False. Implicit reset via condition change is sufficient.
    """
    MOCKED_NOW = datetime.datetime(2026, 3, 20, 14, 0, 0)
    SENT_AT = MOCKED_NOW - datetime.timedelta(hours=8)  # 8h ago — would escalate IF walk hadn't happened

    async def mock_last_sent(msg_type, user_id=None):
        if msg_type == "walk_reminder":
            return SENT_AT
        return None

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},  # user walked — reset condition
        "beeminder_alerts": [],
        "goal_runway": []
    }
    mock_insight = {"momentum": "low", "message": "Good job!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight), log_provider=mock_last_sent)

    class MockAfternoon(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return MOCKED_NOW

    with patch('services.reminder_service.datetime', MockAfternoon):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is False  # walk happened; walk block skipped entirely


@pytest.mark.asyncio
async def test_tier3_not_promoted_by_idle_window():
    """Nag Ladder: beeminder_emergency_tier3 (tier 3) is never downgraded or affected."""

    MOCKED_NOW = datetime.datetime(2026, 3, 20, 8, 0, 0)
    SENT_AT = MOCKED_NOW - datetime.timedelta(hours=7)

    async def mock_last_sent(msg_type, user_id=None):
        # Return old timestamp for any type — would trigger escalation for tier 1
        return SENT_AT

    mock_context = {
        "daily_walk_status": {"has_activity_today": True},
        "beeminder_alerts": [],
        "goal_runway": [
            {"slug": "weight", "title": "Weight Goal", "derail_risk": "CRITICAL", "runway": "1.5 hours"}
        ]
    }
    mock_insight = {"momentum": "low", "message": "Emergency!"}

    rs = ReminderService(make_async_mock(mock_context), make_async_mock(mock_insight), log_provider=mock_last_sent)

    class MockMorning(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return MOCKED_NOW

    with patch('services.reminder_service.datetime', MockMorning):
        result = await rs.check_reminder_needed()
        assert result["should_send"] is True
        assert result["type"] == "beeminder_emergency_tier3"
        assert result["tier"] == 3  # must remain tier 3
