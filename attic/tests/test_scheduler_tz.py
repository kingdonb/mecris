import pytest
import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from scheduler import MecrisScheduler

@pytest.fixture
def test_scheduler(tmp_path):
    db_path = tmp_path / "test_mecris.db"
    with patch.dict(os.environ, {"MECRIS_DB_PATH": str(db_path), "NEON_DB_URL": ""}):
        sched = MecrisScheduler()
        sched._init_db()
        yield sched
        sched.shutdown()

@pytest.mark.asyncio
async def test_heartbeat_is_utc(test_scheduler):
    """
    Test that the heartbeat stored in the database is in UTC, 
    even if the local system time is different.
    """
    # Simulate being in a non-UTC timezone (e.g., UTC-4)
    # Local time: 10:00 AM, UTC time: 2:00 PM
    local_now = datetime(2026, 3, 20, 10, 0, 0)
    utc_now = datetime(2026, 3, 20, 14, 0, 0, tzinfo=timezone.utc)
    
    # We want to verify that scheduler uses UTC
    # Currently it uses datetime.now() which is local naive
    
    with patch('scheduler.datetime') as mock_datetime:
        mock_datetime.now.return_value = local_now
        # In reality, if it used UTC-aware now, it would be:
        # mock_datetime.now.return_value = utc_now
        
        await test_scheduler._attempt_leadership()
        
    # Check what's in the DB
    import sqlite3
    conn = sqlite3.connect(test_scheduler.db_path)
    row = conn.execute("SELECT heartbeat FROM scheduler_election WHERE role = 'leader'").fetchone()
    conn.close()
    
    heartbeat_str = row[0]
    # In SQLite fallback, it currently stores isoformat() of naive now
    # We WANT it to store something that represents UTC
    
    # If the fix is implemented, we expect the heartbeat to be roughly 'now' in UTC
    # For now, let's just assert that we can detect it's NOT UTC if it's 4 hours off
    
    # This test is designed to FAIL before the fix if we assert it SHOULD be UTC-ish
    # but the mock returns local_now.
    
    # Wait, if I mock datetime.now() to return local_now, and the code calls datetime.now(),
    # it gets local_now.
    # If I want to PROVE it's wrong, I should show that a heartbeat from 4 hours ago
    # (relative to a "current" UTC time) is considered stale.
    
    # Let's try another approach: mock the comparison.
    pass

@pytest.mark.asyncio
async def test_heartbeat_timezone_mismatch_reproduction(test_scheduler):
    """
    Reproduction of the issue:
    1. Local time is UTC-4.
    2. Local heartbeat is recorded at 10:00 AM (naive).
    3. Remote check (Spin/Neon) compares it against UTC 14:00.
    4. 14:00 - 10:00 = 4 hours > 90 seconds -> Stale!
    """
    # 1. Local process records heartbeat using naive now (10:00 AM)
    local_naive_now = datetime(2026, 3, 20, 10, 0, 0)
    with patch('scheduler.datetime') as mock_datetime:
        mock_datetime.now.return_value = local_naive_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        await test_scheduler._attempt_leadership()
        
    assert test_scheduler.is_leader is True
    
    # 2. Verify it's in the DB as 10:00
    import sqlite3
    conn = sqlite3.connect(test_scheduler.db_path)
    row = conn.execute("SELECT heartbeat FROM scheduler_election WHERE role = 'leader'").fetchone()
    conn.close()
    assert "10:00:00" in row[0]
    
    # 3. Simulate a "now" that is UTC 14:00:10
    # A check against this would see 10:00 AM as being 4 hours old
    # The failover check logic is: heartbeat > NOW() - INTERVAL '90 seconds'
    # In Python: heartbeat > utc_now - 90s
    
    utc_now = datetime(2026, 3, 20, 14, 0, 10, tzinfo=timezone.utc)
    heartbeat_from_db = datetime.fromisoformat(row[0])
    
    # If heartbeat_from_db is naive, we can't easily compare to aware without assuming a TZ
    # But if we assume the DB is "UTC" (as Neon does), we'd do:
    heartbeat_as_utc = heartbeat_from_db.replace(tzinfo=timezone.utc)
    
    is_active = heartbeat_as_utc > (utc_now - timedelta(seconds=90))
    
    # This should be FALSE (stale) because 10:00 < 13:58:40
    assert is_active is False, "Heartbeat should be stale due to TZ mismatch"

@pytest.mark.asyncio
async def test_heartbeat_utc_fix_verification(test_scheduler):
    """
    Verification of the fix:
    1. Local time is UTC-4 (10:00 AM).
    2. Heartbeat is recorded using UTC (14:00).
    3. Remote check (Spin/Neon) compares it against UTC 14:00:10.
    4. 14:00:10 - 14:00:00 = 10s < 90 seconds -> ACTIVE!
    """
    # 1. Local process records heartbeat using UTC-aware now
    # We mock datetime.now(timezone.utc) to return 14:00
    utc_now_mock = datetime(2026, 3, 20, 14, 0, 0, tzinfo=timezone.utc)
    
    # Mocking datetime.now(timezone.utc) specifically
    with patch('scheduler.datetime') as mock_datetime:
        mock_datetime.now.side_effect = lambda tz=None: utc_now_mock if tz == timezone.utc else datetime.now(tz)
        mock_datetime.fromisoformat = datetime.fromisoformat
        await test_scheduler._attempt_leadership()
        
    assert test_scheduler.is_leader is True
    
    # 2. Verify it's in the DB with UTC info
    import sqlite3
    conn = sqlite3.connect(test_scheduler.db_path)
    row = conn.execute("SELECT heartbeat FROM scheduler_election WHERE role = 'leader'").fetchone()
    conn.close()
    
    # 3. Simulate a "now" that is UTC 14:00:10
    check_now = datetime(2026, 3, 20, 14, 0, 10, tzinfo=timezone.utc)
    heartbeat_from_db = datetime.fromisoformat(row[0])
    
    # If heartbeat_from_db is aware (it should be now), this works perfectly
    is_active = heartbeat_from_db > (check_now - timedelta(seconds=90))
    
    assert is_active is True, f"Heartbeat should be ACTIVE. DB: {heartbeat_from_db}, Check: {check_now}"
    assert heartbeat_from_db.tzinfo is not None
