import pytest
from datetime import datetime, timezone
from ghost.archivist_logic import should_ghost_wake_up

class MockRecord:
    def __init__(self, last_ghost_activity=None, last_human_activity=None):
        self.last_ghost_activity = last_ghost_activity
        self.last_human_activity = last_human_activity

def test_ghost_wakes_up_when_cooldown_passed():
    """Ghost wakes at any time of day once cooldown (12 hours) has elapsed."""
    # 2 PM — previously blocked by night-window restriction; now allowed.
    current_time = datetime(2026, 4, 5, 14, 0, 0, tzinfo=timezone.utc)
    last_activity = datetime(2026, 4, 4, 14, 0, 0, tzinfo=timezone.utc)  # 24h ago
    record = MockRecord(last_ghost_activity=last_activity)

    assert should_ghost_wake_up(record, current_time) is True

def test_ghost_stays_asleep_if_cooldown_not_passed():
    """Ghost stays asleep if fewer than 12 hours have elapsed since last sync."""
    current_time = datetime(2026, 4, 5, 14, 0, 0, tzinfo=timezone.utc)
    last_activity = datetime(2026, 4, 5, 6, 0, 0, tzinfo=timezone.utc)  # 8h ago
    record = MockRecord(last_ghost_activity=last_activity)

    assert should_ghost_wake_up(record, current_time) is False

def test_ghost_wakes_up_even_if_human_was_recently_active():
    """Ghost ignores human presence — continuous reconciliation is human-agnostic."""
    # 3 AM, human was active 30 minutes ago.
    current_time = datetime(2026, 4, 5, 3, 0, 0, tzinfo=timezone.utc)
    last_human = datetime(2026, 4, 5, 2, 30, 0, tzinfo=timezone.utc)
    last_ghost = datetime(2026, 4, 4, 3, 0, 0, tzinfo=timezone.utc)  # 24h ago

    record = MockRecord(last_ghost_activity=last_ghost, last_human_activity=last_human)

    # Human activity should not prevent the ghost from running.
    assert should_ghost_wake_up(record, current_time) is True

def test_ghost_wakes_up_with_no_prior_activity():
    """Ghost wakes immediately if it has never run before."""
    current_time = datetime(2026, 4, 5, 8, 0, 0, tzinfo=timezone.utc)
    record = MockRecord(last_ghost_activity=None)

    assert should_ghost_wake_up(record, current_time) is True
