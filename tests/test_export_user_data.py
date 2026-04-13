"""
Tests for GDPR data portability: export_user_data MCP tool — yebyen/mecris#170.

Covers:
- Happy path: returns data from all 6 tables for a known user
- Unknown user: returns error dict when user_id not found
- No DB: returns error dict when NEON_DB_URL is not configured
- Default user resolution: user_id=None resolves via usage_tracker
"""

import sys
import pytest
from unittest.mock import patch, MagicMock, call


def _make_mcp_importable():
    """Patch env + psycopg2 so mcp_server can be imported without a real DB."""
    return [
        patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}),
        patch("psycopg2.connect"),
    ]


def _make_cursor_with_tables(user_row, table_rows=None):
    """
    Return a mock cursor that serves:
      - fetchall() → [user_row] for the first call (users table SELECT *)
      - fetchall() → [] for subsequent table queries
    cursor.description returns a one-column header [("col",)] by default.
    """
    if table_rows is None:
        table_rows = []

    mock_cur = MagicMock()
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)

    # description is used to build column names; return a single col for simplicity
    mock_cur.description = [("pocket_id_sub",)]

    # First fetchall → users row; subsequent → empty (language_stats, etc.)
    mock_cur.fetchall.side_effect = [[user_row]] + [table_rows] * 5
    return mock_cur


# ---------------------------------------------------------------------------
# export_user_data — happy path
# ---------------------------------------------------------------------------

def test_export_user_data_returns_all_tables():
    """Happy path: exported=True, data dict has all 6 table keys."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()

    mock_conn = MagicMock()
    mock_cur = _make_cursor_with_tables(user_row=("test-user",))
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    with env_patch, db_patch as mock_connect:
        mock_connect.return_value = mock_conn
        from mcp_server import export_user_data
        result = export_user_data(user_id="test-user")

    assert result["exported"] is True
    assert result["user_id"] == "test-user"
    assert "data" in result
    expected_tables = {"users", "language_stats", "budget_tracking", "token_bank", "walk_inferences", "message_log"}
    assert set(result["data"].keys()) == expected_tables


def test_export_user_data_users_table_populated():
    """Happy path: users list contains the user's row."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()

    mock_conn = MagicMock()
    mock_cur = _make_cursor_with_tables(user_row=("test-user",))
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    with env_patch, db_patch as mock_connect:
        mock_connect.return_value = mock_conn
        from mcp_server import export_user_data
        result = export_user_data(user_id="test-user")

    assert len(result["data"]["users"]) == 1
    assert result["data"]["users"][0]["pocket_id_sub"] == "test-user"


# ---------------------------------------------------------------------------
# export_user_data — unknown user
# ---------------------------------------------------------------------------

def test_export_user_data_unknown_user_returns_error():
    """When user does not exist, returns exported=False with error message."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    # users table returns no rows → user not found
    mock_cur.description = [("pocket_id_sub",)]
    mock_cur.fetchall.return_value = []

    with env_patch, db_patch as mock_connect:
        mock_connect.return_value = mock_conn
        from mcp_server import export_user_data
        result = export_user_data(user_id="ghost-user")

    assert result["exported"] is False
    assert "not found" in result["error"].lower()
    assert "data" not in result


# ---------------------------------------------------------------------------
# export_user_data — no DB configured
# ---------------------------------------------------------------------------

def test_export_user_data_no_neon_url():
    """Returns error dict when NEON_DB_URL is not configured at call time."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()

    with env_patch, db_patch:
        from mcp_server import export_user_data
        with patch.dict("os.environ", {"NEON_DB_URL": ""}):
            result = export_user_data(user_id="test-user")

    assert result["exported"] is False
    assert "neon" in result["error"].lower() or "not configured" in result["error"].lower()


# ---------------------------------------------------------------------------
# export_user_data — default user resolution
# ---------------------------------------------------------------------------

def test_export_user_data_resolves_default_user_when_none():
    """When user_id=None, resolves via usage_tracker.resolve_user_id."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()

    mock_conn = MagicMock()
    mock_cur = _make_cursor_with_tables(user_row=("resolved-user",))
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    with env_patch, db_patch as mock_connect:
        mock_connect.return_value = mock_conn
        from mcp_server import export_user_data
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "resolved-user"
            result = export_user_data(user_id=None)

    mock_tracker.resolve_user_id.assert_called_once_with(None)
    assert result["user_id"] == "resolved-user"
