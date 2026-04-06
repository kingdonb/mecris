import pytest
import sys
from unittest.mock import patch, MagicMock
import asyncio

def _make_mcp_importable():
    """Patch env + psycopg2 so mcp_server can be imported without a real DB."""
    return [
        patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}),
        patch("psycopg2.connect"),
    ]

@pytest.mark.asyncio
async def test_trigger_reminder_check_integration():
    """Test that trigger_reminder_check correctly coordinates service and messaging."""

    # Evict any partially-cached mcp_server from prior failed imports
    sys.modules.pop("mcp_server", None)

    mock_reminder_data = {
        "should_send": True,
        "type": "test_reminder",
        "message": "Integrity check"
    }

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value="test-user"):
            with patch("mcp_server.reminder_service.check_reminder_needed", return_value=mock_reminder_data) as mock_check:
                with patch("mcp_server.send_reminder_message", return_value={"sent": True}) as mock_send:
                    from mcp_server import trigger_reminder_check

                    result = await trigger_reminder_check()

                    assert result["triggered"] is True
                    mock_check.assert_called_once()
                    mock_send.assert_called_once()
                    assert mock_send.call_args[0][0] == mock_reminder_data

@pytest.mark.asyncio
async def test_trigger_reminder_check_skips_when_not_needed():
    """Test that trigger_reminder_check stays quiet when no reminder is needed."""

    sys.modules.pop("mcp_server", None)

    mock_reminder_data = {"should_send": False, "reason": "Quiet time"}

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.resolve_target_user", return_value="test-user"):
            with patch("mcp_server.reminder_service.check_reminder_needed", return_value=mock_reminder_data):
                with patch("mcp_server.send_reminder_message") as mock_send:
                    from mcp_server import trigger_reminder_check

                    result = await trigger_reminder_check()

                    assert result["triggered"] is False
                    assert result["reason"] == "Quiet time"
                    mock_send.assert_not_called()
