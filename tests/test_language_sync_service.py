import pytest
from unittest.mock import patch, MagicMock
import asyncio
from datetime import datetime

# We'll need to mock psycopg2 and beeminder_client
@pytest.fixture
def mock_dependencies():
    with patch("psycopg2.connect") as mock_connect:
        with patch("services.language_sync_service.sync_clozemaster_to_beeminder") as mock_scrape:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            
            # Setup connection context
            mock_connect.return_value.__enter__.return_value = mock_conn
            # Setup cursor context
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_cur.fetchone.return_value = None
            
            yield {
                "cursor": mock_cur,
                "scrape": mock_scrape
            }

@pytest.mark.asyncio
async def test_language_sync_service_coordination(mock_dependencies):
    """Test that the service correctly maps scraper data to Beeminder stats and updates Neon."""
    from services.language_sync_service import LanguageSyncService
    
    # 1. Setup mock scraper data
    mock_dependencies["scrape"].return_value = {
        "arabic": {"count": 2600, "forecast": {"tomorrow": 5, "next_7_days": 100}},
        "greek": {"count": 20, "forecast": {"tomorrow": 2, "next_7_days": 40}}
    }
    
    # 2. Setup mock beeminder client
    mock_beeminder = MagicMock()
    mock_beeminder.user_id = None  # match resolved target_user_id so no new BeeminderClient is spawned
    
    async def mock_get_all_goals():
        return [
            {"slug": "reviewstack", "safebuf": 6, "derail_risk": "CAUTION"},
            {"slug": "ellinika", "safebuf": 9, "derail_risk": "SAFE"}
        ]
    mock_beeminder.get_all_goals = mock_get_all_goals
    
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake"}):
        service = LanguageSyncService(mock_beeminder)

        # 3. Run sync
        result = await service.sync_all(dry_run=False)
    # 4. Verify results
    assert result["success"] is True
    assert result["min_safebuf"] == 6
    assert result["arabic"]["count"] == 2600
    assert result["greek"]["count"] == 20

    # 5. Verify the two language_stats UPSERTs happened with correct SQL and mapping
    args_list = mock_dependencies["cursor"].execute.call_args_list
    insert_calls = [c for c in args_list if "INSERT INTO language_stats" in c[0][0]]
    assert len(insert_calls) == 2  # one for Arabic, one for Greek

    # Check INSERT columns are present
    sql = insert_calls[0][0][0]
    assert "safebuf" in sql
    assert "derail_risk" in sql

    # Check mapping logic (Arabic -> reviewstack, safebuf=6 at param index 6)
    arabic_call = next(c for c in insert_calls if c[0][1][1] == "ARABIC")
    arabic_params = arabic_call[0][1]
    assert arabic_params[6] == 6  # safebuf from reviewstack goal


def test_score_delta_backup_detection_updates_daily_completions():
    """When cards_today=0 and points_today=0 but score increased, delta is used as daily_completions."""
    from unittest.mock import patch, MagicMock, call
    from services.language_sync_service import LanguageSyncService

    mock_beeminder = MagicMock()
    service = LanguageSyncService(mock_beeminder)

    # Simulate: last_points=500, current points=600 → delta=100; no upstream "today" data
    scraper_data = {
        "arabic": {
            "count": 50,
            "points": 600,
            "points_today": 0,
            "forecast": {"tomorrow": 0, "next_7_days": 0, "cards_today": 0},
        }
    }
    goal_map = {}
    summary = {"min_safebuf": 999}

    captured_params = []

    def fake_execute(sql, params=None):
        if params:
            captured_params.append((sql, params))

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.execute.side_effect = fake_execute
    # First fetchone: return existing row with last_points=500, daily_completions=0
    mock_cur.fetchone.return_value = (500, 0, datetime(2026, 4, 3, 10, 0, 0))
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)

    with patch("psycopg2.connect", return_value=mock_conn):
        service._update_neon_db(scraper_data, goal_map, summary, "test_user")

    # Find the INSERT call
    insert_calls = [(sql, params) for sql, params in captured_params if "INSERT INTO language_stats" in sql]
    assert len(insert_calls) == 1, "Expected exactly one INSERT call"

    # daily_completions is at index 9 in the INSERT parameter tuple
    insert_params = insert_calls[0][1]
    daily_completions_idx = 9  # (user_id, language_name, current, tomorrow, next_7, daily_rate, safebuf, derail_risk, slug, daily_completions, ...)
    assert insert_params[daily_completions_idx] == 100, (
        f"Expected daily_completions=100 (delta from score), got {insert_params[daily_completions_idx]}"
    )
