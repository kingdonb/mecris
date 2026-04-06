import pytest
from datetime import datetime, time, timezone
from ghost.archivist_logic import should_ghost_wake_up

class MockRecord:
    def __init__(self, last_ghost_activity=None, last_human_activity=None):
        self.last_ghost_activity = last_ghost_activity
        self.last_human_activity = last_human_activity

def test_ghost_wakes_up_during_night_window_if_cooldown_passed():
    """Ghost should wake up between 2 AM and 5 AM local time if cooldown passed."""
    # 3 AM in some timezone
    current_time = datetime(2026, 4, 5, 3, 0, 0, tzinfo=timezone.utc)
    
    # Cooldown passed (last activity 24h ago)
    last_activity = datetime(2026, 4, 4, 3, 0, 0, tzinfo=timezone.utc)
    record = MockRecord(last_ghost_activity=last_activity)
    
    # This should return True once we implement the window logic
    assert should_ghost_wake_up(record, current_time) is True

def test_ghost_stays_asleep_outside_night_window():
    """Ghost should not wake up at 2 PM even if cooldown passed."""
    # 2 PM
    current_time = datetime(2026, 4, 5, 14, 0, 0, tzinfo=timezone.utc)
    
    last_activity = datetime(2026, 4, 4, 14, 0, 0, tzinfo=timezone.utc)
    record = MockRecord(last_ghost_activity=last_activity)
    
    # This should fail (returns True currently because only cooldown is checked)
    assert should_ghost_wake_up(record, current_time) is False

def test_ghost_stays_asleep_if_human_was_recent():
    """Ghost should not wake up if human was active in last 1 hour."""
    # 3 AM (inside window)
    current_time = datetime(2026, 4, 5, 3, 0, 0, tzinfo=timezone.utc)
    
    # Human was active 30 mins ago
    last_human = datetime(2026, 4, 5, 2, 30, 0, tzinfo=timezone.utc)
    last_ghost = datetime(2026, 4, 4, 3, 0, 0, tzinfo=timezone.utc)
    
    record = MockRecord(last_ghost_activity=last_ghost)
    record.last_human_activity = last_human
    
    # This should fail (returns True currently because human activity isn't checked)
    assert should_ghost_wake_up(record, current_time) is False
