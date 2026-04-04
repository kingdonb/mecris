import pytest
from datetime import datetime, timezone, time
from ghost.presence import PresenceRecord, StatusType
from ghost.archivist_logic import should_ghost_wake_up

def test_ghost_wakes_up_when_silent_at_night():
    # 13 hours ago (silent > 12h)
    last_human = datetime(2026, 4, 4, 8, 0, 0, tzinfo=timezone.utc)
    # 10:30 PM (within window)
    current_time = datetime(2026, 4, 4, 22, 30, 0, tzinfo=timezone.utc)
    
    record = PresenceRecord(
        user_id="user1",
        last_active=last_human,
        last_human_activity=last_human,
        last_ghost_activity=None,
        source="cli",
        status_type=StatusType.ACTIVE_HUMAN
    )
    
    assert should_ghost_wake_up(record, current_time) is True

def test_ghost_stays_asleep_during_day():
    # 13 hours ago (silent > 12h)
    last_human = datetime(2026, 4, 4, 8, 0, 0, tzinfo=timezone.utc)
    # 2:00 PM (outside window)
    current_time = datetime(2026, 4, 4, 14, 0, 0, tzinfo=timezone.utc)
    
    record = PresenceRecord(
        user_id="user1",
        last_active=last_human,
        last_human_activity=last_human,
        last_ghost_activity=None,
        source="cli",
        status_type=StatusType.ACTIVE_HUMAN
    )
    
    assert should_ghost_wake_up(record, current_time) is False

def test_ghost_stays_asleep_if_human_active_recently():
    # 2 hours ago (not silent)
    last_human = datetime(2026, 4, 4, 20, 30, 0, tzinfo=timezone.utc)
    # 10:30 PM (within window)
    current_time = datetime(2026, 4, 4, 22, 30, 0, tzinfo=timezone.utc)
    
    record = PresenceRecord(
        user_id="user1",
        last_active=last_human,
        last_human_activity=last_human,
        last_ghost_activity=None,
        source="cli",
        status_type=StatusType.ACTIVE_HUMAN
    )
    
    assert should_ghost_wake_up(record, current_time) is False

def test_ghost_stays_asleep_if_already_synced():
    # 13 hours ago (silent > 12h)
    last_human = datetime(2026, 4, 4, 8, 0, 0, tzinfo=timezone.utc)
    # Ghost active 1 hour ago
    last_ghost = datetime(2026, 4, 4, 21, 30, 0, tzinfo=timezone.utc)
    # 10:30 PM (within window)
    current_time = datetime(2026, 4, 4, 22, 30, 0, tzinfo=timezone.utc)
    
    record = PresenceRecord(
        user_id="user1",
        last_active=last_ghost,
        last_human_activity=last_human,
        last_ghost_activity=last_ghost,
        source="cli",
        status_type=StatusType.ACTIVE_GHOST
    )
    
    assert should_ghost_wake_up(record, current_time) is False
