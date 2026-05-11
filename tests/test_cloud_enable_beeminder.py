"""
Unit tests for scripts/cloud_enable_beeminder.py

Covers sync_beeminder_to_cloud():
  - Returns early when NEON_DB_URL is missing
  - Returns early when BEEMINDER_AUTH_TOKEN is missing
  - Calls UPDATE and commits when rowcount > 0
  - Falls back to INSERT when UPDATE rowcount == 0
  - Handles DB exceptions gracefully
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Bootstrap heavy dependencies before importing the module
_mock_psycopg2 = MagicMock()
sys.modules.setdefault("psycopg2", _mock_psycopg2)
sys.modules.setdefault("dotenv", MagicMock())

# Now import the function under test
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from cloud_enable_beeminder import sync_beeminder_to_cloud


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cursor(rowcount: int = 1) -> MagicMock:
    cur = MagicMock()
    cur.rowcount = rowcount
    return cur


def _make_conn(cur: MagicMock) -> MagicMock:
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


_GOOD_ENV = {
    "NEON_DB_URL": "postgresql://fake/db",
    "BEEMINDER_AUTH_TOKEN": "tok123",
    "BEEMINDER_USERNAME": "testuser",
    "DEFAULT_USER_ID": "user-sub-abc",
}


# ---------------------------------------------------------------------------
# Early-exit guards
# ---------------------------------------------------------------------------

class TestEarlyExitGuards:
    def test_missing_db_url_returns_without_connecting(self, capsys):
        env = {**_GOOD_ENV, "NEON_DB_URL": ""}
        with patch.dict("os.environ", env, clear=True):
            sync_beeminder_to_cloud()
        out = capsys.readouterr().out
        assert "Missing configuration" in out
        _mock_psycopg2.connect.assert_not_called()

    def test_missing_beeminder_token_returns_without_connecting(self, capsys):
        env = {**_GOOD_ENV, "BEEMINDER_AUTH_TOKEN": ""}
        with patch.dict("os.environ", env, clear=True):
            sync_beeminder_to_cloud()
        out = capsys.readouterr().out
        assert "Missing configuration" in out
        _mock_psycopg2.connect.assert_not_called()


# ---------------------------------------------------------------------------
# Successful UPDATE path (rowcount > 0)
# ---------------------------------------------------------------------------

class TestSuccessfulUpdatePath:
    def test_commits_after_update(self, capsys):
        cur = _make_cursor(rowcount=1)
        conn = _make_conn(cur)

        with (
            patch.dict("os.environ", _GOOD_ENV, clear=True),
            patch("psycopg2.connect", return_value=conn),
            patch("cloud_enable_beeminder.EncryptionService") as mock_enc_cls,
        ):
            mock_enc = MagicMock()
            mock_enc.encrypt.side_effect = lambda v: f"enc({v})"
            mock_enc_cls.return_value = mock_enc
            sync_beeminder_to_cloud()

        conn.commit.assert_called_once()
        out = capsys.readouterr().out
        assert "complete" in out.lower()

    def test_does_not_insert_when_update_succeeds(self, capsys):
        cur = _make_cursor(rowcount=1)
        conn = _make_conn(cur)

        with (
            patch.dict("os.environ", _GOOD_ENV, clear=True),
            patch("psycopg2.connect", return_value=conn),
            patch("cloud_enable_beeminder.EncryptionService") as mock_enc_cls,
        ):
            mock_enc = MagicMock()
            mock_enc.encrypt.side_effect = lambda v: f"enc({v})"
            mock_enc_cls.return_value = mock_enc
            sync_beeminder_to_cloud()

        # Only the UPDATE should have been executed (one execute call)
        assert cur.execute.call_count == 1
        sql = cur.execute.call_args[0][0]
        assert "UPDATE" in sql


# ---------------------------------------------------------------------------
# Fallback INSERT path (rowcount == 0)
# ---------------------------------------------------------------------------

class TestFallbackInsertPath:
    def test_inserts_when_update_finds_no_user(self, capsys):
        cur = _make_cursor(rowcount=0)
        conn = _make_conn(cur)

        with (
            patch.dict("os.environ", _GOOD_ENV, clear=True),
            patch("psycopg2.connect", return_value=conn),
            patch("cloud_enable_beeminder.EncryptionService") as mock_enc_cls,
        ):
            mock_enc = MagicMock()
            mock_enc.encrypt.side_effect = lambda v: f"enc({v})"
            mock_enc_cls.return_value = mock_enc
            sync_beeminder_to_cloud()

        assert cur.execute.call_count == 2
        insert_sql = cur.execute.call_args_list[1][0][0]
        assert "INSERT" in insert_sql

    def test_warns_when_user_not_found(self, capsys):
        cur = _make_cursor(rowcount=0)
        conn = _make_conn(cur)

        with (
            patch.dict("os.environ", _GOOD_ENV, clear=True),
            patch("psycopg2.connect", return_value=conn),
            patch("cloud_enable_beeminder.EncryptionService") as mock_enc_cls,
        ):
            mock_enc = MagicMock()
            mock_enc.encrypt.side_effect = lambda v: f"enc({v})"
            mock_enc_cls.return_value = mock_enc
            sync_beeminder_to_cloud()

        out = capsys.readouterr().out
        assert "Warning" in out or "not found" in out


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------

class TestExceptionHandling:
    def test_db_exception_is_caught(self, capsys):
        with (
            patch.dict("os.environ", _GOOD_ENV, clear=True),
            patch("psycopg2.connect", side_effect=RuntimeError("connection refused")),
            patch("cloud_enable_beeminder.EncryptionService"),
        ):
            # Should not raise
            sync_beeminder_to_cloud()

        out = capsys.readouterr().out
        assert "error" in out.lower() or "Error" in out
