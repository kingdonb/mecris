import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
import zoneinfo
from scripts.clozemaster_scraper import sync_clozemaster_to_beeminder

@pytest.fixture
def mock_scraper():
    with patch("scripts.clozemaster_scraper.ClozemasterScraper") as mock:
        instance = mock.return_value
        instance.login = AsyncMock(return_value=True)
        instance.close = AsyncMock()
        instance.get_review_forecast = AsyncMock()
        yield instance

@pytest.fixture
def mock_beeminder():
    with patch("scripts.clozemaster_scraper.BeeminderClient") as mock:
        instance = mock.return_value
        instance.get_all_goals = AsyncMock()
        instance.get_goal_datapoints = AsyncMock()
        instance.add_datapoint = AsyncMock()
        instance.close = AsyncMock()
        yield instance

@pytest.mark.asyncio
async def test_clozemaster_sync_idempotency(mock_scraper, mock_beeminder):
    """Test that the sync process correctly skips duplicate datapoints."""

    # 1. Setup mock data
    # Arabic goal with 2600 reviews
    mock_scraper.get_review_forecast.side_effect = [
        {"today": 2600, "tomorrow": 5, "next_7_days": 100} # Arabic
    ]

    # Existing goals on Beeminder
    mock_beeminder.get_all_goals.return_value = [
        {"slug": "reviewstack"}
    ]

    # Setup today's date in Eastern time for matching
    eastern = zoneinfo.ZoneInfo("US/Eastern")
    now_eastern = datetime.now(eastern)
    today_start = now_eastern.replace(hour=0, minute=0, second=0, microsecond=0)
    today_ts = int(today_start.timestamp())

    # Simulation scenario:
    # Arabic already has a datapoint today with value 2600.

    mock_beeminder.get_goal_datapoints.side_effect = [
        [{"value": 2600.0, "timestamp": today_ts + 3600}] # Arabic: already exists
    ]

    mock_beeminder.add_datapoint.return_value = True

    # 2. Run the sync
    results = await sync_clozemaster_to_beeminder(dry_run=False)

    # 3. Verify results
    assert results is not None
    assert results["arabic"]["count"] == 2600
    assert "greek" not in results # Greek sync is disabled in the scraper

    # 4. Verify Beeminder calls
    # Should check datapoints for Arabic only
    assert mock_beeminder.get_goal_datapoints.call_count == 1
    
    # Should NOT have called add_datapoint because value is identical
    assert mock_beeminder.add_datapoint.call_count == 0

@pytest.mark.asyncio
async def test_clozemaster_sync_new_value_pushed(mock_scraper, mock_beeminder):
    """Test that a new value (even if same day) is pushed."""

    mock_scraper.get_review_forecast.side_effect = [
        {"today": 2550, "tomorrow": 5, "next_7_days": 100} # Arabic (changed from 2600)
    ]

    mock_beeminder.get_all_goals.return_value = [
        {"slug": "reviewstack"}
    ]

    eastern = zoneinfo.ZoneInfo("US/Eastern")
    now_eastern = datetime.now(eastern)
    today_start = now_eastern.replace(hour=0, minute=0, second=0, microsecond=0)
    today_ts = int(today_start.timestamp())

    # Arabic already has 2600 today, but new value is 2550
    mock_beeminder.get_goal_datapoints.side_effect = [
        [{"value": 2600.0, "timestamp": today_ts + 3600}] # Arabic: 2600 exists
    ]

    mock_beeminder.add_datapoint.return_value = True

    # 2. Run the sync
    await sync_clozemaster_to_beeminder(dry_run=False)

    # 3. Verify Beeminder calls
    # Should push ONLY for Arabic
    assert mock_beeminder.add_datapoint.call_count == 1
    assert mock_beeminder.add_datapoint.call_args[0][0] == "reviewstack"
    assert mock_beeminder.add_datapoint.call_args[0][1] == 2550.0
