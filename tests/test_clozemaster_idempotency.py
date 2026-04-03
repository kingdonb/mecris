import pytest
from unittest.mock import MagicMock, patch, AsyncMock, call
from datetime import datetime
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
        instance.add_datapoint = AsyncMock(return_value=True)
        instance.close = AsyncMock()
        yield instance


@pytest.mark.asyncio
async def test_clozemaster_sync_pushes_with_requestid(mock_scraper, mock_beeminder):
    """add_datapoint is always called with a deterministic requestid."""
    mock_scraper.get_review_forecast.side_effect = [
        {"today": 2600, "tomorrow": 5, "next_7_days": 100}
    ]
    mock_beeminder.get_all_goals.return_value = [{"slug": "reviewstack"}]

    await sync_clozemaster_to_beeminder(dry_run=False)

    assert mock_beeminder.add_datapoint.call_count == 1
    _, kwargs = mock_beeminder.add_datapoint.call_args
    assert "requestid" in kwargs
    assert kwargs["requestid"].startswith("reviewstack-")


@pytest.mark.asyncio
async def test_clozemaster_sync_requestid_format(mock_scraper, mock_beeminder):
    """requestid is {goal_slug}-{YYYY-MM-DD} in Eastern time."""
    mock_scraper.get_review_forecast.side_effect = [
        {"today": 42, "tomorrow": 0, "next_7_days": 0}
    ]
    mock_beeminder.get_all_goals.return_value = [{"slug": "reviewstack"}]

    eastern = zoneinfo.ZoneInfo("US/Eastern")
    expected_date = datetime.now(eastern).strftime("%Y-%m-%d")
    expected_requestid = f"reviewstack-{expected_date}"

    await sync_clozemaster_to_beeminder(dry_run=False)

    _, kwargs = mock_beeminder.add_datapoint.call_args
    assert kwargs["requestid"] == expected_requestid


@pytest.mark.asyncio
async def test_clozemaster_sync_does_not_prefetch_datapoints(mock_scraper, mock_beeminder):
    """get_goal_datapoints is never called — requestid handles deduplication server-side."""
    mock_scraper.get_review_forecast.side_effect = [
        {"today": 2600, "tomorrow": 5, "next_7_days": 100}
    ]
    mock_beeminder.get_all_goals.return_value = [{"slug": "reviewstack"}]

    await sync_clozemaster_to_beeminder(dry_run=False)

    assert mock_beeminder.get_goal_datapoints.call_count == 0


@pytest.mark.asyncio
async def test_clozemaster_sync_dry_run_no_push(mock_scraper, mock_beeminder):
    """Dry run skips both the push and requestid generation."""
    mock_scraper.get_review_forecast.side_effect = [
        {"today": 2600, "tomorrow": 5, "next_7_days": 100}
    ]
    mock_beeminder.get_all_goals.return_value = [{"slug": "reviewstack"}]

    results = await sync_clozemaster_to_beeminder(dry_run=True)

    assert results["arabic"]["count"] == 2600
    assert mock_beeminder.add_datapoint.call_count == 0


@pytest.mark.asyncio
async def test_clozemaster_sync_skips_unknown_goal(mock_scraper, mock_beeminder):
    """Goals not on Beeminder are skipped without calling add_datapoint."""
    mock_scraper.get_review_forecast.side_effect = [
        {"today": 2600, "tomorrow": 5, "next_7_days": 100}
    ]
    mock_beeminder.get_all_goals.return_value = []  # reviewstack not present

    await sync_clozemaster_to_beeminder(dry_run=False)

    assert mock_beeminder.add_datapoint.call_count == 0
