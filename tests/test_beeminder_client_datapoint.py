"""Unit tests for BeeminderClient.add_datapoint — daystamp parameter behavior.

Tests the behavioral changes from kingdonb commit 9bdf4e75:
- daystamp provided → data["daystamp"] used instead of data["timestamp"]
- daystamp absent → data["timestamp"] set (current epoch)
- requestid → included in POST body when provided
- return value → True if _api_call returns a result, False if None
"""
import pytest
from unittest.mock import AsyncMock, patch
from beeminder_client import BeeminderClient


def _make_client() -> BeeminderClient:
    """Create a BeeminderClient with credentials pre-set to skip _load_credentials."""
    client = BeeminderClient(user_id=None)
    client.username = "testuser"
    client.auth_token = "fake-token"
    return client


@pytest.mark.asyncio
async def test_add_datapoint_with_daystamp_uses_daystamp_not_timestamp():
    """When daystamp is provided, POST data must contain daystamp and must NOT contain timestamp."""
    client = _make_client()
    captured = {}

    async def fake_api_call(endpoint, method="GET", data=None):
        captured["data"] = dict(data or {})
        return {"id": 1}

    with patch.object(client, "_api_call", side_effect=fake_api_call):
        result = await client.add_datapoint("groqspend", 0.05, comment="test", daystamp="20260413")

    assert result is True
    assert "daystamp" in captured["data"]
    assert captured["data"]["daystamp"] == "20260413"
    assert "timestamp" not in captured["data"]


@pytest.mark.asyncio
async def test_add_datapoint_without_daystamp_uses_timestamp():
    """When daystamp is not provided, POST data must contain timestamp and must NOT contain daystamp."""
    client = _make_client()
    captured = {}

    async def fake_api_call(endpoint, method="GET", data=None):
        captured["data"] = dict(data or {})
        return {"id": 2}

    with patch.object(client, "_api_call", side_effect=fake_api_call):
        result = await client.add_datapoint("bike", 1.0)

    assert result is True
    assert "timestamp" in captured["data"]
    assert isinstance(captured["data"]["timestamp"], int)
    assert "daystamp" not in captured["data"]


@pytest.mark.asyncio
async def test_add_datapoint_with_requestid_includes_requestid():
    """When requestid is provided, it must appear in POST data."""
    client = _make_client()
    captured = {}

    async def fake_api_call(endpoint, method="GET", data=None):
        captured["data"] = dict(data or {})
        return {"id": 3}

    with patch.object(client, "_api_call", side_effect=fake_api_call):
        await client.add_datapoint("bike", 1.0, requestid="unique-req-123")

    assert captured["data"]["requestid"] == "unique-req-123"


@pytest.mark.asyncio
async def test_add_datapoint_without_requestid_excludes_requestid():
    """When requestid is not provided, it must NOT appear in POST data."""
    client = _make_client()
    captured = {}

    async def fake_api_call(endpoint, method="GET", data=None):
        captured["data"] = dict(data or {})
        return {"id": 4}

    with patch.object(client, "_api_call", side_effect=fake_api_call):
        await client.add_datapoint("bike", 1.0)

    assert "requestid" not in captured["data"]


@pytest.mark.asyncio
async def test_add_datapoint_returns_true_when_api_call_succeeds():
    """Returns True when _api_call returns a non-None result."""
    client = _make_client()

    with patch.object(client, "_api_call", new_callable=AsyncMock, return_value={"id": 5}):
        result = await client.add_datapoint("groqspend", 0.1)

    assert result is True


@pytest.mark.asyncio
async def test_add_datapoint_returns_false_when_api_call_returns_none():
    """Returns False when _api_call returns None (API error path)."""
    client = _make_client()

    with patch.object(client, "_api_call", new_callable=AsyncMock, return_value=None):
        result = await client.add_datapoint("groqspend", 0.1)

    assert result is False


@pytest.mark.asyncio
async def test_add_datapoint_posts_to_correct_endpoint():
    """Endpoint must be users/{username}/goals/{goal_slug}/datapoints.json."""
    client = _make_client()
    captured = {}

    async def fake_api_call(endpoint, method="GET", data=None):
        captured["endpoint"] = endpoint
        captured["method"] = method
        return {"id": 6}

    with patch.object(client, "_api_call", side_effect=fake_api_call):
        await client.add_datapoint("groqspend", 0.05)

    assert captured["endpoint"] == "users/testuser/goals/groqspend/datapoints.json"
    assert captured["method"] == "POST"
