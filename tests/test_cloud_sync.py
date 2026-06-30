"""
Tests for the synchronous /internal/cloud-sync endpoint.

Covers:
- Endpoint returns {"status": "success", ...} on success.
- sync_all is awaited synchronously inside the handler body.
- Exceptions in sync_all propagate as HTTP 500 exceptions.
"""

import asyncio
import sys

import pytest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException


def _make_mcp_importable():
    """Patch env + psycopg2 so mcp_server can be imported without a real DB."""
    return [
        patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}),
        patch("psycopg2.connect"),
    ]


@pytest.mark.asyncio
async def test_cloud_sync_returns_success_status():
    """Endpoint returns status='success' and a completion message."""
    sys.modules.pop("mcp_server", None)

    mock_sync = AsyncMock(return_value={"synced": 5})
    env_patch, db_patch = _make_mcp_importable()

    with env_patch, db_patch:
        with patch("mcp_server.language_sync_service") as mock_service:
            mock_service.sync_all = mock_sync
            from mcp_server import trigger_cloud_sync_endpoint
            result = await trigger_cloud_sync_endpoint(user_id="test-user")

    assert result["status"] == "success"
    assert result["message"] == "Cloud sync complete"


@pytest.mark.asyncio
async def test_cloud_sync_sync_all_called_synchronously():
    """sync_all is called and awaited synchronously during the request."""
    sys.modules.pop("mcp_server", None)

    mock_sync = AsyncMock(return_value={"synced": 3})
    env_patch, db_patch = _make_mcp_importable()

    with env_patch, db_patch:
        with patch("mcp_server.language_sync_service") as mock_service:
            mock_service.sync_all = mock_sync
            from mcp_server import trigger_cloud_sync_endpoint

            result = await trigger_cloud_sync_endpoint(user_id="test-user")

            assert result["status"] == "success"
            # sync_all has already been awaited when trigger_cloud_sync_endpoint returns
            mock_service.sync_all.assert_awaited_once_with(user_id="test-user")


@pytest.mark.asyncio
async def test_cloud_sync_exception_propagates_as_http_500():
    """Exception raised by sync_all propagates as HTTPException with 500 status."""
    sys.modules.pop("mcp_server", None)

    mock_sync = AsyncMock(side_effect=RuntimeError("Clozemaster scraper down"))
    env_patch, db_patch = _make_mcp_importable()

    with env_patch, db_patch:
        with patch("mcp_server.language_sync_service") as mock_service:
            mock_service.sync_all = mock_sync
            from mcp_server import trigger_cloud_sync_endpoint

            # Exception must propagate as HTTP 500
            with pytest.raises(HTTPException) as exc_info:
                await trigger_cloud_sync_endpoint(user_id="test-user")
            
            assert exc_info.value.status_code == 500
            assert "Clozemaster scraper down" in exc_info.value.detail

    mock_service.sync_all.assert_awaited_once()
