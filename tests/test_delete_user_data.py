"""
Tests for GDPR right-to-erasure: delete_user_data MCP tool — yebyen/mecris#167.

Covers:
- Happy path: deletes from token_bank then users; CASCADE handles the rest
- Unknown user: returns error dict when user_id not found in users table
- No DB: returns error dict when NEON_DB_URL is not configured
- Unknown user guard uses SELECT before DELETE (no blind deletes)
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


# ---------------------------------------------------------------------------
# delete_user_data — happy path
# ---------------------------------------------------------------------------

def test_delete_user_data_deletes_token_bank_then_users():
    """Happy path: deletes token_bank row then users row; CASCADE handles rest."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    # SELECT returns 1 row (user exists)
    mock_cur.fetchone.return_value = ("test-user",)

    with env_patch, db_patch as mock_connect:
        mock_connect.return_value = mock_conn
        from mcp_server import delete_user_data
        result = delete_user_data(user_id="test-user")

    assert result["deleted"] is True
    assert result["user_id"] == "test-user"

    # Verify SQL calls: SELECT first, then DELETE token_bank, then DELETE users
    executed_sqls = [str(c.args[0]).strip() for c in mock_cur.execute.call_args_list]
    assert any("SELECT" in sql and "users" in sql for sql in executed_sqls), \
        f"Expected SELECT from users, got: {executed_sqls}"
    assert any("DELETE FROM token_bank" in sql for sql in executed_sqls), \
        f"Expected DELETE from token_bank, got: {executed_sqls}"
    assert any("DELETE FROM users" in sql for sql in executed_sqls), \
        f"Expected DELETE from users, got: {executed_sqls}"

    # token_bank DELETE must come before users DELETE
    token_bank_idx = next(i for i, s in enumerate(executed_sqls) if "DELETE FROM token_bank" in s)
    users_idx = next(i for i, s in enumerate(executed_sqls) if "DELETE FROM users" in s)
    assert token_bank_idx < users_idx, "token_bank must be deleted before users"


def test_delete_user_data_unknown_user_returns_error():
    """When user does not exist, returns error dict without deleting."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    # SELECT returns no row (user not found)
    mock_cur.fetchone.return_value = None

    with env_patch, db_patch as mock_connect:
        mock_connect.return_value = mock_conn
        from mcp_server import delete_user_data
        result = delete_user_data(user_id="ghost-user")

    assert result["deleted"] is False
    assert "not found" in result["error"].lower()

    # No DELETE statements should have been issued
    executed_sqls = [str(c.args[0]).strip() for c in mock_cur.execute.call_args_list]
    assert not any("DELETE FROM" in sql for sql in executed_sqls), \
        f"Should not DELETE when user not found, got: {executed_sqls}"


def test_delete_user_data_no_neon_url():
    """Returns error dict when NEON_DB_URL is not configured at call time."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()

    with env_patch, db_patch:
        from mcp_server import delete_user_data
        # Remove NEON_DB_URL at call time (module already imported safely above)
        with patch.dict("os.environ", {"NEON_DB_URL": ""}):
            result = delete_user_data(user_id="test-user")

    assert result["deleted"] is False
    assert "neon" in result["error"].lower() or "not configured" in result["error"].lower()


def test_delete_user_data_resolves_default_user_when_none():
    """When user_id=None, resolves via usage_tracker.resolve_user_id."""
    sys.modules.pop("mcp_server", None)

    env_patch, db_patch = _make_mcp_importable()

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = ("resolved-user",)

    with env_patch, db_patch as mock_connect:
        mock_connect.return_value = mock_conn
        from mcp_server import delete_user_data
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "resolved-user"
            result = delete_user_data(user_id=None)

    mock_tracker.resolve_user_id.assert_called_once_with(None)
    assert result["user_id"] == "resolved-user"
