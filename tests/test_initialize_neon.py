"""
Unit tests for scripts/initialize_neon.py initialize_neon() function.

All psycopg2 I/O and filesystem access are mocked. No DB or network required.
Groups:
  - TestInitializeNeonEarlyReturn (2): missing NEON_DB_URL or schema file absent
  - TestInitializeNeonSuccess (1): happy path — connects, reads SQL, executes, commits

Total: 3 tests
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open


# ---------------------------------------------------------------------------
# Bootstrap: mock psycopg2 and dotenv before importing the module
# ---------------------------------------------------------------------------

_mock_psycopg2 = MagicMock()
sys.modules.setdefault("psycopg2", _mock_psycopg2)
sys.modules.setdefault("dotenv", MagicMock())

from scripts.initialize_neon import initialize_neon  # noqa: E402


# ---------------------------------------------------------------------------
# TestInitializeNeonEarlyReturn
# ---------------------------------------------------------------------------

class TestInitializeNeonEarlyReturn:
    def test_no_neon_db_url_returns_early(self):
        """initialize_neon() exits without touching psycopg2 when NEON_DB_URL is absent."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEON_DB_URL", None)
            with patch.object(sys.modules["psycopg2"], "connect") as mock_connect:
                initialize_neon()
                mock_connect.assert_not_called()

    def test_schema_file_missing_returns_early(self):
        """initialize_neon() exits without touching psycopg2 when schema file is absent."""
        env = {"NEON_DB_URL": "postgresql://fake"}
        with patch.dict(os.environ, env, clear=True):
            with patch("os.path.exists", return_value=False):
                with patch.object(sys.modules["psycopg2"], "connect") as mock_connect:
                    initialize_neon()
                    mock_connect.assert_not_called()


# ---------------------------------------------------------------------------
# TestInitializeNeonSuccess
# ---------------------------------------------------------------------------

class TestInitializeNeonSuccess:
    def test_successful_execution_connects_and_commits(self):
        """Happy path: connects to DB, reads schema SQL, executes it, and commits."""
        schema_sql = "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY);"
        env = {"NEON_DB_URL": "postgresql://fake"}

        cur = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value = cur

        with patch.dict(os.environ, env, clear=True):
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=schema_sql)):
                    with patch.object(sys.modules["psycopg2"], "connect", return_value=conn):
                        initialize_neon()

        cur.execute.assert_called_once_with(schema_sql)
        conn.commit.assert_called_once()
        cur.close.assert_called_once()
        conn.close.assert_called_once()
