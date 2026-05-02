"""
Unit tests for scripts/migrate_review_pump.py migrate() function.

All psycopg2 I/O is mocked. No DB or network access required.
Groups:
  - TestMigrateEarlyReturn (1): missing NEON_DB_URL returns immediately
  - TestMigrateSuccess (1): ALTER TABLE pump_multiplier issued and committed
  - TestMigrateFailure (1): DB exception is caught and logged without raise

Total: 3 tests
"""

import sys
import os
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: mock psycopg2 before importing the module
# ---------------------------------------------------------------------------

_mock_psycopg2 = MagicMock()
sys.modules.setdefault("psycopg2", _mock_psycopg2)

from scripts.migrate_review_pump import migrate  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_cursor():
    cur = MagicMock()
    cur.__enter__ = lambda s: s
    cur.__exit__ = MagicMock(return_value=False)
    return cur


def _make_mock_conn(cursor):
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
            with patch.object(sys.modules["psycopg2"], "connect") as mock_connect:
                migrate()
                mock_connect.assert_not_called()


# ---------------------------------------------------------------------------
# TestMigrateSuccess
# ---------------------------------------------------------------------------

class TestMigrateSuccess:
    def test_alter_table_pump_multiplier_issued_and_committed(self):
        """ALTER TABLE language_stats ADD COLUMN pump_multiplier is executed and committed."""
        cur = _make_mock_cursor()
        conn = _make_mock_conn(cur)

        with patch.dict(os.environ, {"NEON_DB_URL": "postgresql://fake"}, clear=True):
            with patch.object(sys.modules["psycopg2"], "connect", return_value=conn):
                migrate()

        executed_sql = [str(c.args[0]).strip() for c in cur.execute.call_args_list]
        assert any(
            "ALTER TABLE" in sql and "pump_multiplier" in sql
            for sql in executed_sql
        )
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# TestMigrateFailure
# ---------------------------------------------------------------------------

class TestMigrateFailure:
    def test_db_exception_is_caught_without_raise(self):
        """When psycopg2.connect raises, migrate() catches the exception and does not re-raise."""
        with patch.dict(os.environ, {"NEON_DB_URL": "postgresql://fake"}, clear=True):
            with patch.object(sys.modules["psycopg2"], "connect", side_effect=Exception("conn failed")):
                # Should not raise
                migrate()
