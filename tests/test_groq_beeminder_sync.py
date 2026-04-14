import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

def _make_mcp_importable():
    """Patch env + psycopg2 so mcp_server can be imported without a real DB."""
    return [
        patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}),
        patch("psycopg2.connect"),
    ]

@pytest.mark.asyncio
async def test_record_groq_reading_syncs_to_beeminder():
    """record_groq_reading calls add_datapoint on BeeminderClient."""
    sys.modules.pop("mcp_server", None)
    sys.modules.pop("groq_odometer_tracker", None)

    mock_tracker_result = {
        "recorded": True,
        "month": "2026-04",
        "cumulative_value": 0.05,
        "reset_detected": False,
        "timestamp": "2026-04-13T12:00:00+00:00"
    }

    mock_beem_client = AsyncMock()
    mock_beem_client.add_datapoint = AsyncMock(return_value=True)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.record_groq_reading_from_tracker", return_value=mock_tracker_result), \
             patch("mcp_server.get_user_beeminder_client", return_value=mock_beem_client), \
             patch("mcp_server.resolve_target_user", return_value="test-user"):
            
            from mcp_server import record_groq_reading
            result = await record_groq_reading(0.05, notes="Test note")
            
            assert result["recorded"] is True
            assert result["beeminder_sync"] == "success"
            
            # Verify BeeminderClient.add_datapoint was called correctly
            mock_beem_client.add_datapoint.assert_called_once_with(
                "groqspend", 0.05, comment="Test note", daystamp="20260413"
            )

@pytest.mark.asyncio
async def test_record_groq_reading_handles_tare_reset():
    """record_groq_reading sends @TARE datapoint when reset_detected is True."""
    sys.modules.pop("mcp_server", None)
    sys.modules.pop("groq_odometer_tracker", None)

    mock_tracker_result = {
        "recorded": True,
        "month": "2026-05",
        "cumulative_value": 0.02,
        "reset_detected": True,
        "timestamp": "2026-05-01T12:00:00+00:00"
    }

    mock_beem_client = AsyncMock()
    mock_beem_client.add_datapoint = AsyncMock(return_value=True)

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.record_groq_reading_from_tracker", return_value=mock_tracker_result), \
             patch("mcp_server.get_user_beeminder_client", return_value=mock_beem_client), \
             patch("mcp_server.resolve_target_user", return_value="test-user"):
            
            from mcp_server import record_groq_reading
            result = await record_groq_reading(0.02)
            
            assert result["reset_detected"] is True
            
            # Verify TWO calls to add_datapoint: 1 for @TARE, 1 for the reading
            assert mock_beem_client.add_datapoint.call_count == 2
            
            # First call should be @TARE
            args0 = mock_beem_client.add_datapoint.call_args_list[0]
            assert args0[0][0] == "groqspend"
            assert args0[0][1] == 0.0
            assert "@TARE" in args0[1]["comment"]
            assert args0[1]["daystamp"] == "20260501"
            
            # Second call should be the reading
            args1 = mock_beem_client.add_datapoint.call_args_list[1]
            assert args1[0][0] == "groqspend"
            assert args1[0][1] == 0.02
            assert args1[1]["daystamp"] == "20260501"

@pytest.mark.asyncio
async def test_record_groq_reading_skips_before_start_date():
    """record_groq_reading skips sync if date is before GROQSPEND_START_DATE."""
    sys.modules.pop("mcp_server", None)
    sys.modules.pop("groq_odometer_tracker", None)

    mock_tracker_result = {
        "recorded": True,
        "month": "2026-04",
        "cumulative_value": 0.01,
        "reset_detected": False,
        "timestamp": "2026-04-12T12:00:00+00:00" # One day before start date
    }

    mock_beem_client = AsyncMock()

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.record_groq_reading_from_tracker", return_value=mock_tracker_result), \
             patch("mcp_server.get_user_beeminder_client", return_value=mock_beem_client), \
             patch("mcp_server.resolve_target_user", return_value="test-user"):
            
            from mcp_server import record_groq_reading
            result = await record_groq_reading(0.01)
            
            assert result["recorded"] is True
            # beeminder_sync key should NOT be in result if it was skipped
            assert "beeminder_sync" not in result
            mock_beem_client.add_datapoint.assert_not_called()

@pytest.mark.asyncio
async def test_record_groq_reading_fails_gracefully_on_beeminder_error():
    """record_groq_reading still returns recorded=True if Beeminder sync fails."""
    sys.modules.pop("mcp_server", None)
    sys.modules.pop("groq_odometer_tracker", None)

    mock_tracker_result = {
        "recorded": True,
        "month": "2026-04",
        "cumulative_value": 0.05,
        "reset_detected": False,
        "timestamp": "2026-04-13T12:00:00+00:00"
    }

    mock_beem_client = AsyncMock()
    mock_beem_client.add_datapoint.side_effect = Exception("API Down")

    env_patch, db_patch = _make_mcp_importable()
    with env_patch, db_patch:
        with patch("mcp_server.record_groq_reading_from_tracker", return_value=mock_tracker_result), \
             patch("mcp_server.get_user_beeminder_client", return_value=mock_beem_client), \
             patch("mcp_server.resolve_target_user", return_value="test-user"):
            
            from mcp_server import record_groq_reading
            result = await record_groq_reading(0.05)
            
            assert result["recorded"] is True
            assert "failed" in result["beeminder_sync"]
