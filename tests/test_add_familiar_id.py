"""
Unit tests for scripts/add_familiar_id.py migrate() function.

All psycopg2 I/O is mocked. No DB or network access required.
Groups:
  - TestMigrateEarlyReturn (1): missing NEON_DB_URL returns immediately
  - TestMigrateColumnExists (1): familiar_id column already present — no ALTER
  - TestMigrateColumnAbsent (1): familiar_id column missing — ALTER TABLE executed
  - TestMigrateUpdateUser (2): with / without DEFAULT_USER_ID set

Total: 5 tests
"""

import sys
import types
import os
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Bootstrap: mock psycopg2 before importing the module
# ---------------------------------------------------------------------------

_mock_psycopg2 = MagicMock()
sys.modules.setdefault("psycopg2", _mock_psycopg2)

from scripts.add_familiar_id import migrate  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_mock_cursor(fetchone_result=None):
    """Return a mock cursor with configurable fetchone()."""
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_result
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    return cur


def _make_mock_conn(cursor):
    """Return a mock connection that yields cursor as a context manager."""
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = lambda s: s
    conn.__exit__ = MagicMock(return_value=False)
    return conn


# ---------------------------------------------------------------------------
# TestMigrateEarlyReturn
# ---------------------------------------------------------------------------

class TestMigrateEarlyReturn:
    def test_no_neon_db_url_returns_immediately(self):
        """migrate() exits before touching psycopg2 when NEON_DB_URL is absent."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEON_DB_URL", None)
            with patch("psycopg2.connect") as mock_connect:
                migrate()
                mock_connect.assert_not_called()


# ---------------------------------------------------------------------------
# TestMigrateColumnExists
# ---------------------------------------------------------------------------

class TestMigrateColumnExists:
    def test_column_already_present_skips_alter(self):
        """When familiar_id column exists, ALTER TABLE is not issued."""
        cur = _make_mock_cursor(fetchone_result=(1,))  # column found
        conn = _make_mock_conn(cur)
        env = {"NEON_DB_URL": "postgresql://fake", "DEFAULT_USER_ID": ""}

        with patch.dict(os.environ, env, clear=True):
            with patch("psycopg2.connect", return_value=conn):
                migrate()

        executed_sql = [str(c.args[0]).strip() for c in cur.execute.call_args_list]
        assert not any("ALTER TABLE" in sql for sql in executed_sql)
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# TestMigrateColumnAbsent
# ---------------------------------------------------------------------------

class TestMigrateColumnAbsent:
    def test_column_absent_issues_alter(self):
        """When familiar_id column is missing, ALTER TABLE ADD COLUMN is executed."""
        cur = _make_mock_cursor(fetchone_result=None)  # column not found
        conn = _make_mock_conn(cur)
        env = {"NEON_DB_URL": "postgresql://fake", "DEFAULT_USER_ID": ""}

        with patch.dict(os.environ, env, clear=True):
            with patch("psycopg2.connect", return_value=conn):
                migrate()

        executed_sql = [str(c.args[0]).strip() for c in cur.execute.call_args_list]
        assert any("ALTER TABLE" in sql and "familiar_id" in sql for sql in executed_sql)
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# TestMigrateUpdateUser
# ---------------------------------------------------------------------------

class TestMigrateUpdateUser:
    def test_with_default_user_id_issues_update(self):
        """When DEFAULT_USER_ID is set, UPDATE users SET familiar_id is executed."""
        cur = _make_mock_cursor(fetchone_result=(1,))
        conn = _make_mock_conn(cur)
        env = {"NEON_DB_URL": "postgresql://fake", "DEFAULT_USER_ID": "user-abc-123"}

        with patch.dict(os.environ, env, clear=True):
            with patch("psycopg2.connect", return_value=conn):
                migrate()

        # Check that an UPDATE call was made with 'yebyen' as the familiar_id value
        update_calls = [
            c for c in cur.execute.call_args_list
            if "UPDATE" in str(c.args[0]) and "familiar_id" in str(c.args[0])
        ]
        assert len(update_calls) == 1
        params = update_calls[0].args[1]
        assert params[0] == "yebyen"
        assert params[1] == "user-abc-123"

    def test_without_default_user_id_skips_update(self):
        """When DEFAULT_USER_ID is absent, UPDATE is not issued."""
        cur = _make_mock_cursor(fetchone_result=(1,))
        conn = _make_mock_conn(cur)
        env = {"NEON_DB_URL": "postgresql://fake"}

        with patch.dict(os.environ, env, clear=True):
            os.environ.pop("DEFAULT_USER_ID", None)
            with patch("psycopg2.connect", return_value=conn):
                migrate()

        executed_sql = [str(c.args[0]).strip() for c in cur.execute.call_args_list]
        assert not any("UPDATE" in sql for sql in executed_sql)
        conn.commit.assert_called_once()
