import pytest
from datetime import datetime, timezone, timedelta
from ghost.presence import PresenceRecord, StatusType
from ghost.archivist_logic import should_ghost_wake_up

def test_ghost_wakes_up_regardless_of_human_activity():
    # Human was active 1 minute ago
    # Mock time to be inside the Archivist's Hour (2 AM - 5 AM UTC)
    current_time = datetime(2026, 4, 4, 3, 0, 0, tzinfo=timezone.utc)
    # Satisfy human silence heuristic (at least 1 hour)
    last_human = current_time - timedelta(minutes=70)
    
    record = PresenceRecord(
        user_id="user1",
        last_active=last_human,
        last_human_activity=last_human,
        last_ghost_activity=None,  # Never synced
        source="cli",
        status_type=StatusType.ACTIVE_HUMAN
    )
    
    # Should wake up even if human is active, because ghost hasn't synced
    assert should_ghost_wake_up(record, current_time) is True

def test_ghost_stays_asleep_if_recently_synced():
    current_time = datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc)
    last_ghost = current_time - timedelta(hours=1) # Synced 1 hour ago
    
    record = PresenceRecord(
        user_id="user1",
        last_active=last_ghost,
        last_human_activity=None,
        last_ghost_activity=last_ghost,
        source="archivist",
        status_type=StatusType.ACTIVE_GHOST
    )
    
    # Should stay asleep because of cooldown (e.g., 12 hours)
    assert should_ghost_wake_up(record, current_time) is False

def test_ghost_wakes_up_after_cooldown():
    current_time = datetime(2026, 4, 4, 3, 0, 0, tzinfo=timezone.utc)
    last_ghost = current_time - timedelta(hours=13) # Synced 13 hours ago
    
    record = PresenceRecord(
        user_id="user1",
        last_active=last_ghost,
        last_human_activity=None,
        last_ghost_activity=last_ghost,
        source="archivist",
        status_type=StatusType.ACTIVE_GHOST
    )
    
    # Should wake up because cooldown has elapsed
    assert should_ghost_wake_up(record, current_time) is True
