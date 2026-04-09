"""
Tests for the async /internal/cloud-sync endpoint (yebyen/mecris#133).

Covers behavioral changes introduced in commit 66396ee:
- Endpoint returns {"status": "accepted", ...} immediately (202 fire-and-forget)
- sync_all is called via asyncio.create_task (not awaited in the handler body)
- Exceptions in the background task are swallowed and do not propagate to the caller
"""

import asyncio
import sys

import pytest
from unittest.mock import patch, AsyncMock


def _make_mcp_importable():
    """Patch env + psycopg2 so mcp_server can be imported without a real DB."""
    return [
        patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}),
        patch("psycopg2.connect"),
    ]


@pytest.mark.asyncio
async def test_cloud_sync_returns_accepted_status():
    """Endpoint returns status='accepted' and a guidance message immediately."""
    sys.modules.pop("mcp_server", None)

    mock_sync = AsyncMock(return_value={"synced": 5})
    env_patch, db_patch = _make_mcp_importable()

    with env_patch, db_patch:
        with patch("mcp_server.language_sync_service") as mock_service:
            mock_service.sync_all = mock_sync
            from mcp_server import trigger_cloud_sync_endpoint
            result = await trigger_cloud_sync_endpoint(user_id="test-user")

    assert result["status"] == "accepted"
    assert "message" in result
    # Message must guide the caller to check /languages rather than waiting on this call
    assert "/languages" in result["message"] or "moments" in result["message"]


@pytest.mark.asyncio
async def test_cloud_sync_sync_all_called_via_background_task():
    """sync_all is not called until the event loop yields (fire-and-forget semantics)."""
    sys.modules.pop("mcp_server", None)

    mock_sync = AsyncMock(return_value={"synced": 3})
    env_patch, db_patch = _make_mcp_importable()

    with env_patch, db_patch:
        with patch("mcp_server.language_sync_service") as mock_service:
            mock_service.sync_all = mock_sync
            from mcp_server import trigger_cloud_sync_endpoint

            result = await trigger_cloud_sync_endpoint(user_id="test-user")

            # Endpoint returns immediately — sync_all has not been awaited yet
            assert result["status"] == "accepted"
            mock_service.sync_all.assert_not_awaited()

            # Yield to the event loop so the background task can run
            await asyncio.sleep(0)

            # sync_all now called exactly once with the correct user_id
            mock_service.sync_all.assert_awaited_once_with(user_id="test-user")


@pytest.mark.asyncio
async def test_cloud_sync_exception_in_background_does_not_propagate():
    """Exception raised by sync_all is swallowed; endpoint response is unaffected."""
    sys.modules.pop("mcp_server", None)

    mock_sync = AsyncMock(side_effect=RuntimeError("Clozemaster scraper down"))
    env_patch, db_patch = _make_mcp_importable()

    with env_patch, db_patch:
        with patch("mcp_server.language_sync_service") as mock_service:
            mock_service.sync_all = mock_sync
            from mcp_server import trigger_cloud_sync_endpoint

            # Must not raise even though sync_all will fail
            result = await trigger_cloud_sync_endpoint(user_id="test-user")
            assert result["status"] == "accepted"

            # Let the background task run — exception must not propagate out
            await asyncio.sleep(0)

    # Reaching here without an unhandled exception confirms isolation
    mock_service.sync_all.assert_awaited_once()
