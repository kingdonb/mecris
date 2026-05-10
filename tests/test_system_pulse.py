"""Tests for fetch_system_pulse() Bus Standardization — kingdonb/mecris#245, yebyen/mecris#337.

Covers:
- Modalities include last_status/intent/last_error when DB columns return values
- Fields default to None when columns are NULL (pre-migration or unset)
- Empty result set returns {"modalities": []}
- unknown_cloud role is skipped
- Display name mapping for known roles
- No NEON_DB_URL → returns empty modalities
"""

import sys
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

_FAKE_HB = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)


def _make_conn_mock(rows):
    """Build a psycopg2 connection mock returning rows from fetchall."""
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchall.return_value = rows

    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    return conn, cur


def _base_patches(conn):
    env_patch = patch.dict(
        "os.environ",
        {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"},
    )
    db_patch = patch("psycopg2.connect", return_value=conn)
    return env_patch, db_patch


@pytest.mark.asyncio
async def test_obs_fields_included_when_present():
    """Modalities include last_status/intent/last_error when DB columns return values."""
    sys.modules.pop("mcp_server", None)
    rows = [("leader", _FAKE_HB, 2.0, "Heartbeat active", "maintain leadership", None)]
    conn, _ = _make_conn_mock(rows)
    env_patch, db_patch = _base_patches(conn)

    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            result = await fetch_system_pulse("test-user")

    assert len(result["modalities"]) == 1
    mod = result["modalities"][0]
    assert mod["last_status"] == "Heartbeat active"
    assert mod["intent"] == "maintain leadership"
    assert mod["last_error"] is None


@pytest.mark.asyncio
async def test_obs_fields_none_when_null():
    """Fields default to None when columns are NULL (pre-migration or not yet written)."""
    sys.modules.pop("mcp_server", None)
    rows = [("leader", _FAKE_HB, 1.5, None, None, None)]
    conn, _ = _make_conn_mock(rows)
    env_patch, db_patch = _base_patches(conn)

    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            result = await fetch_system_pulse("test-user")

    assert len(result["modalities"]) == 1
    mod = result["modalities"][0]
    assert mod["last_status"] is None
    assert mod["intent"] is None
    assert mod["last_error"] is None


@pytest.mark.asyncio
async def test_empty_result_returns_empty_modalities():
    """Empty result set returns {"modalities": []}."""
    sys.modules.pop("mcp_server", None)
    conn, _ = _make_conn_mock([])
    env_patch, db_patch = _base_patches(conn)

    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            result = await fetch_system_pulse("test-user")

    assert result == {"modalities": []}


@pytest.mark.asyncio
async def test_unknown_cloud_role_skipped():
    """unknown_cloud rows are excluded from modalities."""
    sys.modules.pop("mcp_server", None)
    rows = [
        ("unknown_cloud", _FAKE_HB, 5.0, None, None, None),
        ("leader", _FAKE_HB, 2.0, "Heartbeat active", "maintain leadership", None),
    ]
    conn, _ = _make_conn_mock(rows)
    env_patch, db_patch = _base_patches(conn)

    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            result = await fetch_system_pulse("test-user")

    assert len(result["modalities"]) == 1
    assert result["modalities"][0]["role"] == "MCP SERVER"


@pytest.mark.asyncio
async def test_display_name_mapping():
    """Known roles are mapped to human-friendly display names."""
    sys.modules.pop("mcp_server", None)
    rows = [
        ("akamai_functions", _FAKE_HB, 3.0, None, None, None),
        ("fermyon_cloud", _FAKE_HB, 4.0, None, None, None),
        ("android_client", _FAKE_HB, 5.0, None, None, None),
    ]
    conn, _ = _make_conn_mock(rows)
    env_patch, db_patch = _base_patches(conn)

    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            result = await fetch_system_pulse("test-user")

    roles = [m["role"] for m in result["modalities"]]
    assert "AKAMAI FUNCTIONS" in roles
    assert "FERMYON CLOUD" in roles
    assert "ANDROID CLIENT" in roles


@pytest.mark.asyncio
async def test_no_neon_url_returns_empty():
    """Returns empty modalities when NEON_DB_URL is not set at call time."""
    sys.modules.pop("mcp_server", None)

    # Import with NEON_DB_URL so mcp_server module-level init succeeds,
    # then call the function without NEON_DB_URL to exercise the early-return guard.
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}):
        with patch("psycopg2.connect"):
            from mcp_server import fetch_system_pulse

    with patch.dict("os.environ", {}, clear=True):
        result = await fetch_system_pulse("test-user")

    assert result == {"modalities": []}
