import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from datetime import datetime, timezone
import zoneinfo

# Add project root to path for local imports is not needed here as it's in the root
from scripts.clozemaster_scraper import sync_clozemaster_to_beeminder

@pytest.fixture
def mock_beeminder():
    with patch("scripts.clozemaster_scraper.BeeminderClient") as mock:
        instance = mock.return_value
        instance.get_all_goals = AsyncMock()
        instance.get_goal_datapoints = AsyncMock()
        instance.add_datapoint = AsyncMock()
        instance.close = AsyncMock()
        yield instance

@pytest.fixture
def mock_scraper():
    with patch("scripts.clozemaster_scraper.ClozemasterScraper") as mock:
        instance = mock.return_value
        instance.login = AsyncMock(return_value=True)
        instance.get_review_forecast = AsyncMock()
        instance.close = AsyncMock()
        yield instance

@pytest.mark.asyncio
async def test_clozemaster_sync_idempotency(mock_scraper, mock_beeminder):
    """Test that the sync process correctly skips duplicate datapoints."""
    
    # 1. Setup mock data
    # Arabic goal with 2600 reviews
    mock_scraper.get_review_forecast.side_effect = [
        {"today": 2600, "tomorrow": 5, "next_7_days": 100}, # Arabic
        {"today": 20, "tomorrow": 2, "next_7_days": 40}    # Greek
    ]
    
    # Existing goals on Beeminder
    mock_beeminder.get_all_goals.return_value = [
        {"slug": "reviewstack"},
        {"slug": "ellinika"}
    ]
    
    # Setup today's date in Eastern time for matching
    eastern = zoneinfo.ZoneInfo("US/Eastern")
    now_eastern = datetime.now(eastern)
    today_start = now_eastern.replace(hour=0, minute=0, second=0, microsecond=0)
    today_ts = int(today_start.timestamp())
    
    # Simulation scenario: 
    # Arabic already has a datapoint today with value 2600.
    # Greek has no datapoints today.
    
    mock_beeminder.get_goal_datapoints.side_effect = [
        [{"value": 2600.0, "timestamp": today_ts + 3600}], # Arabic: already exists
        [] # Greek: new value
    ]
    
    mock_beeminder.add_datapoint.return_value = True
    
    # 2. Run the sync
    results = await sync_clozemaster_to_beeminder(dry_run=False)
    
    # 3. Verify results
    assert results is not None
    assert results["arabic"]["count"] == 2600
    assert results["greek"]["count"] == 20
    
    # 4. Verify Beeminder calls
    # Should check datapoints for both
    assert mock_beeminder.get_goal_datapoints.call_count == 2
    
    # Should ONLY push for Greek (since Arabic was a duplicate)
    assert mock_beeminder.add_datapoint.call_count == 1
    
    # Verify the call was for Greek
    args, kwargs = mock_beeminder.add_datapoint.call_args
    assert args[0] == "ellinika"
    assert args[1] == 20.0

@pytest.mark.asyncio
async def test_clozemaster_sync_new_value_pushed(mock_scraper, mock_beeminder):
    """Test that a new value (even if same day) is pushed."""
    
    mock_scraper.get_review_forecast.side_effect = [
        {"today": 2550, "tomorrow": 5, "next_7_days": 100}, # Arabic (changed from 2600)
        {"today": 20, "tomorrow": 2, "next_7_days": 40}    # Greek
    ]
    
    mock_beeminder.get_all_goals.return_value = [
        {"slug": "reviewstack"},
        {"slug": "ellinika"}
    ]
    
    eastern = zoneinfo.ZoneInfo("US/Eastern")
    now_eastern = datetime.now(eastern)
    today_start = now_eastern.replace(hour=0, minute=0, second=0, microsecond=0)
    today_ts = int(today_start.timestamp())
    
    # Arabic already has 2600 today, but new value is 2550
    mock_beeminder.get_goal_datapoints.side_effect = [
        [{"value": 2600.0, "timestamp": today_ts + 3600}], # Arabic: 2600 exists
        [] # Greek
    ]
    
    mock_beeminder.add_datapoint.return_value = True
    
    # 2. Run the sync
    await sync_clozemaster_to_beeminder(dry_run=False)
    
    # 3. Verify Beeminder calls
    # Should push for BOTH because Arabic value changed
    assert mock_beeminder.add_datapoint.call_count == 2
    
    # First call should be Arabic with new value
    # Note: order depends on dict iteration, but both should be called
    called_slugs = [call[0][0] for call in mock_beeminder.add_datapoint.call_args_list]
    assert "reviewstack" in called_slugs
    assert "ellinika" in called_slugs
