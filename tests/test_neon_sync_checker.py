import pytest
import datetime
import zoneinfo
from unittest.mock import patch, MagicMock
from services.neon_sync_checker import NeonSyncChecker

@pytest.fixture
def mock_psycopg2():
    with patch("services.neon_sync_checker.psycopg2") as mock_pg:
        # Setup mock connection and cursor
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pg.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        yield mock_cur

def test_neon_checker_no_url():
    """Test that it safely returns False if NEON_DB_URL is missing."""
    with patch.dict("os.environ", clear=True):
        checker = NeonSyncChecker()
        assert checker.has_walk_today() is False
        assert checker.get_latest_walk() is None

@patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake"})
def test_neon_checker_has_walk_today_true(mock_psycopg2):
    """Test that it returns True if the database count is > 0."""
    checker = NeonSyncChecker()
    mock_psycopg2.fetchone.return_value = [1] # 1 walk found
    
    # Mock datetime to ensure stable test environment
    eastern = zoneinfo.ZoneInfo("US/Eastern")
    mock_now = datetime.datetime(2026, 3, 20, 15, 0, tzinfo=eastern)
    
    with patch("services.neon_sync_checker.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        result = checker.has_walk_today()
        
        assert result is True
        # Verify it queries against Eastern midnight
        expected_midnight = datetime.datetime(2026, 3, 20, 0, 0)
        
        # Check the execute call arguments
        args, kwargs = mock_psycopg2.execute.call_args
        query = args[0]
        params = args[1]
        
        assert "US/Eastern" in query
        assert params[0] == expected_midnight

@patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake"})
def test_neon_checker_has_walk_today_false(mock_psycopg2):
    """Test that it returns False if the database count is 0."""
    checker = NeonSyncChecker()
    mock_psycopg2.fetchone.return_value = [0] # 0 walks found
    
    result = checker.has_walk_today()
    assert result is False

@patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake"})
def test_get_language_stats_includes_beeminder_slug_and_safebuf(mock_psycopg2):
    """Fix: f62ad68 — get_language_stats must return beeminder_slug and safebuf from DB."""
    checker = NeonSyncChecker()
    # 8-column row: name, current, tomorrow, next_7, multiplier, daily_completions, beeminder_slug, safebuf
    mock_psycopg2.fetchall.return_value = [
        ("Arabic", 2600, 5, 100, 2.0, 50, "reviewstack", 3),
        ("Greek", 20, 2, 40, 1.0, 10, None, 0),
    ]

    result = checker.get_language_stats(user_id="yebyen")

    assert "arabic" in result
    assert result["arabic"]["beeminder_slug"] == "reviewstack"
    assert result["arabic"]["safebuf"] == 3
    assert "greek" in result
    assert result["greek"]["beeminder_slug"] is None
    assert result["greek"]["safebuf"] == 0

@patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake"})
def test_neon_checker_get_latest_walk(mock_psycopg2):
    """Test that it correctly maps the database row to a dictionary."""
    checker = NeonSyncChecker()
    
    mock_time = datetime.datetime.now(datetime.timezone.utc)
    mock_psycopg2.fetchone.return_value = [mock_time, 3500, 2500.0, "Health Connect"]
    
    result = checker.get_latest_walk()
    
    assert result is not None
    assert result["step_count"] == 3500
    assert result["distance_meters"] == 2500.0
    assert result["distance_source"] == "Health Connect"
    assert result["start_time"] == mock_time