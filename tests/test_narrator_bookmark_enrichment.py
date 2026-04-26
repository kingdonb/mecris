"""
Tests for Narrator bookmark enrichment in get_narrator_context (yebyen/mecris#281 / kingdonb/mecris#208 phase 2).

Verifies that:
- _enrich_bookmarks_for_narrator returns an empty list when no bookmarks file exists
- _enrich_bookmarks_for_narrator deduplicates by URL and annotates goal_slug
- _enrich_bookmarks_for_narrator sorts goals by derail_risk (CRITICAL first)
- get_narrator_context response includes a `related_bookmarks` key
- get_narrator_context gracefully returns [] when enrichment raises an exception
"""

import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ---------------------------------------------------------------------------
# Unit tests for _enrich_bookmarks_for_narrator (pure logic, no imports needed)
# ---------------------------------------------------------------------------

def _make_bookmark(title: str, url: str) -> dict:
    # Chrome bookmarks use "name" for the title; _flatten_node converts it to "title"
    return {"name": title, "url": url, "type": "url", "date_added": "0"}


def _make_fake_bookmarks(*bookmarks) -> dict:
    """Wrap bookmark nodes in a Chrome-format structure with a proper folder root."""
    return {
        "roots": {
            "bookmark_bar": {
                "name": "Bookmarks bar",
                "type": "folder",
                "children": list(bookmarks),
            }
        }
    }


def test_enrich_returns_empty_when_no_bookmarks_file():
    """Returns [] gracefully when load_bookmarks returns empty (file not found)."""
    sys.modules.pop("mcp_server", None)

    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}):
        with patch("psycopg2.connect"):
            with patch("tools.chrome_bookmarks.load_bookmarks", return_value={}):
                from mcp_server import _enrich_bookmarks_for_narrator
                result = _enrich_bookmarks_for_narrator([{"slug": "python", "title": "python", "derail_risk": "SAFE"}])
    assert result == []


def test_enrich_returns_matches_for_known_goal():
    """Returns bookmark matches when bookmarks file exists and query matches."""
    sys.modules.pop("mcp_server", None)

    fake_bookmarks = _make_fake_bookmarks(
        _make_bookmark("Python asyncio docs", "https://docs.python.org/asyncio"),
        _make_bookmark("Dog walking tips", "https://example.com/dogs"),
    )

    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}):
        with patch("psycopg2.connect"):
            with patch("tools.chrome_bookmarks.load_bookmarks", return_value=fake_bookmarks):
                from mcp_server import _enrich_bookmarks_for_narrator
                goals = [{"slug": "python", "title": "Python asyncio", "derail_risk": "CRITICAL"}]
                result = _enrich_bookmarks_for_narrator(goals)

    assert len(result) >= 1
    assert result[0]["url"] == "https://docs.python.org/asyncio"
    assert result[0]["goal_slug"] == "python"
    assert "score" in result[0]


def test_enrich_deduplicates_by_url():
    """Same URL from two different goal queries appears only once."""
    sys.modules.pop("mcp_server", None)

    fake_bookmarks = _make_fake_bookmarks(
        _make_bookmark("Python asyncio docs", "https://docs.python.org/asyncio"),
    )

    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}):
        with patch("psycopg2.connect"):
            with patch("tools.chrome_bookmarks.load_bookmarks", return_value=fake_bookmarks):
                from mcp_server import _enrich_bookmarks_for_narrator
                goals = [
                    {"slug": "python", "title": "Python asyncio", "derail_risk": "CRITICAL"},
                    {"slug": "python2", "title": "Python asyncio programming", "derail_risk": "WARNING"},
                ]
                result = _enrich_bookmarks_for_narrator(goals)

    urls = [r["url"] for r in result]
    assert len(urls) == len(set(urls)), "Duplicate URLs found in enrichment results"


def test_enrich_critical_goals_queried_first():
    """CRITICAL goals are queried before SAFE goals, so their matches appear first."""
    sys.modules.pop("mcp_server", None)

    fake_bookmarks = _make_fake_bookmarks(
        _make_bookmark("Python docs", "https://docs.python.org"),
        _make_bookmark("Walking health tips", "https://example.com/walk"),
    )

    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}):
        with patch("psycopg2.connect"):
            with patch("tools.chrome_bookmarks.load_bookmarks", return_value=fake_bookmarks):
                from mcp_server import _enrich_bookmarks_for_narrator
                goals = [
                    {"slug": "walk", "title": "Walking", "derail_risk": "CRITICAL"},
                    {"slug": "python", "title": "Python", "derail_risk": "SAFE"},
                ]
                result = _enrich_bookmarks_for_narrator(goals)

    if len(result) >= 2:
        assert result[0]["goal_slug"] == "walk", (
            f"Expected CRITICAL goal 'walk' first, got: {result[0]['goal_slug']}"
        )


# ---------------------------------------------------------------------------
# Integration test: get_narrator_context includes related_bookmarks key
# ---------------------------------------------------------------------------

def _base_env():
    return {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}


def _make_narrator_mocks():
    tracker = MagicMock()
    tracker.resolve_user_id.return_value = "test-user"
    tracker.get_goals.return_value = []
    tracker.get_budget_status.return_value = {"days_remaining": 5.0, "remaining_budget": 10.0}

    client = MagicMock()
    client.get_emergencies = AsyncMock(return_value=[])
    client.get_runway_summary = AsyncMock(return_value=[])

    neon = MagicMock()
    neon.get_language_stats.return_value = {"arabic": {"next_7_days": 0}, "greek": {"next_7_days": 0}}
    neon.get_latest_walk.return_value = None

    lang_sync = MagicMock()
    lang_sync._greek_backlog_active.return_value = False

    weather = MagicMock()
    weather.get_weather.return_value = {}
    weather.is_walk_appropriate.return_value = (True, "Weather fine")

    scheduler = MagicMock()
    scheduler.running = True
    scheduler.is_leader = True
    scheduler.process_id = "test-pid"

    governor = MagicMock()
    governor.get_narrator_summary.return_value = {}

    return {
        "tracker": tracker, "client": client, "neon": neon,
        "lang_sync": lang_sync, "weather": weather,
        "scheduler": scheduler, "governor": governor,
    }


async def _run_narrator_context(enrich_return_value=None):
    """Run get_narrator_context with all deps mocked; patch _enrich_bookmarks_for_narrator."""
    sys.modules.pop("mcp_server", None)
    mocks = _make_narrator_mocks()
    if enrich_return_value is None:
        enrich_return_value = []

    aggregate = {"score": "0/0", "satisfied_count": 0, "total_count": 0, "all_clear": True, "goals": []}

    with patch.dict("os.environ", _base_env()):
        with patch("psycopg2.connect"):
            with patch("mcp_server.usage_tracker", mocks["tracker"]):
                with patch("mcp_server.resolve_target_user", return_value="test-user"):
                    with patch("mcp_server._record_presence", AsyncMock()):
                        with patch("mcp_server.obsidian_client") as mock_obs:
                            mock_obs.get_todos = AsyncMock(return_value=[])
                            with patch("mcp_server.get_cached_beeminder_goals", AsyncMock(return_value=[])):
                                with patch("mcp_server.get_user_beeminder_client", return_value=mocks["client"]):
                                    with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value={"status": "done", "has_activity_today": True})):
                                        with patch("mcp_server.get_groq_context_for_narrator", return_value={}):
                                            with patch("mcp_server.neon_checker", mocks["neon"]):
                                                with patch("mcp_server.language_sync_service", mocks["lang_sync"]):
                                                    with patch("mcp_server.weather_service", mocks["weather"]):
                                                        with patch("mcp_server.scheduler", mocks["scheduler"]):
                                                            with patch("mcp_server._budget_governor", mocks["governor"]):
                                                                with patch("mcp_server._get_presence_summary", AsyncMock(return_value={})):
                                                                    with patch("mcp_server.anthropic_cost_tracker", None):
                                                                        with patch("mcp_server.get_daily_aggregate_status", AsyncMock(return_value=aggregate)):
                                                                            with patch("mcp_server._enrich_bookmarks_for_narrator", return_value=enrich_return_value):
                                                                                from mcp_server import get_narrator_context
                                                                                return await get_narrator_context()


@pytest.mark.asyncio
async def test_narrator_context_includes_related_bookmarks_key():
    """get_narrator_context result always includes a related_bookmarks key."""
    result = await _run_narrator_context(enrich_return_value=[])
    assert "related_bookmarks" in result


@pytest.mark.asyncio
async def test_narrator_context_related_bookmarks_empty_when_no_file():
    """related_bookmarks is [] when enrichment returns no results."""
    result = await _run_narrator_context(enrich_return_value=[])
    assert result["related_bookmarks"] == []


@pytest.mark.asyncio
async def test_narrator_context_related_bookmarks_populated():
    """related_bookmarks reflects matches returned by _enrich_bookmarks_for_narrator."""
    fake_match = {"title": "Python docs", "url": "https://docs.python.org", "score": 0.9, "goal_slug": "python"}
    result = await _run_narrator_context(enrich_return_value=[fake_match])
    assert result["related_bookmarks"] == [fake_match]


@pytest.mark.asyncio
async def test_narrator_context_enrichment_failure_does_not_crash():
    """If _enrich_bookmarks_for_narrator raises, related_bookmarks is [] and context still returns."""
    sys.modules.pop("mcp_server", None)
    mocks = _make_narrator_mocks()
    aggregate = {"score": "0/0", "satisfied_count": 0, "total_count": 0, "all_clear": True, "goals": []}

    with patch.dict("os.environ", _base_env()):
        with patch("psycopg2.connect"):
            with patch("mcp_server.usage_tracker", mocks["tracker"]):
                with patch("mcp_server.resolve_target_user", return_value="test-user"):
                    with patch("mcp_server._record_presence", AsyncMock()):
                        with patch("mcp_server.obsidian_client") as mock_obs:
                            mock_obs.get_todos = AsyncMock(return_value=[])
                            with patch("mcp_server.get_cached_beeminder_goals", AsyncMock(return_value=[])):
                                with patch("mcp_server.get_user_beeminder_client", return_value=mocks["client"]):
                                    with patch("mcp_server.get_cached_daily_activity", AsyncMock(return_value={"status": "done", "has_activity_today": True})):
                                        with patch("mcp_server.get_groq_context_for_narrator", return_value={}):
                                            with patch("mcp_server.neon_checker", mocks["neon"]):
                                                with patch("mcp_server.language_sync_service", mocks["lang_sync"]):
                                                    with patch("mcp_server.weather_service", mocks["weather"]):
                                                        with patch("mcp_server.scheduler", mocks["scheduler"]):
                                                            with patch("mcp_server._budget_governor", mocks["governor"]):
                                                                with patch("mcp_server._get_presence_summary", AsyncMock(return_value={})):
                                                                    with patch("mcp_server.anthropic_cost_tracker", None):
                                                                        with patch("mcp_server.get_daily_aggregate_status", AsyncMock(return_value=aggregate)):
                                                                            with patch("mcp_server._enrich_bookmarks_for_narrator", side_effect=RuntimeError("disk error")):
                                                                                from mcp_server import get_narrator_context
                                                                                result = await get_narrator_context()

    assert "summary" in result
    assert result.get("related_bookmarks") == []
