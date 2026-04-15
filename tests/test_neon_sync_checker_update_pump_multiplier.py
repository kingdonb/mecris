"""Unit tests for NeonSyncChecker.update_pump_multiplier — yebyen/mecris#186.

Covers all three control-flow branches:
  no db_url → False
  successful UPDATE + commit → True
  DB exception → False

Also verifies the language_name.upper() normalization and SQL param ordering.
"""
import pytest
from unittest.mock import patch, MagicMock

from services.neon_sync_checker import NeonSyncChecker

FAKE_URL = "postgres://fake"
FAKE_UUID = "abc-123-uuid"


@pytest.fixture
def checker():
    """Checker with NEON_DB_URL set and resolve_user_id stubbed to return FAKE_UUID."""
    with patch.dict("os.environ", {"NEON_DB_URL": FAKE_URL}):
        c = NeonSyncChecker()
    with patch.object(c, "resolve_user_id", return_value=FAKE_UUID):
        yield c


def test_update_pump_multiplier_no_db_url():
    """Returns False immediately when db_url is not set (no DB call made)."""
    with patch.dict("os.environ", {"NEON_DB_URL": FAKE_URL}):
        checker = NeonSyncChecker()
    checker.db_url = None
    result = checker.update_pump_multiplier("Arabic", 2.0)
    assert result is False


def test_update_pump_multiplier_success(checker):
    """Returns True after a successful UPDATE + commit."""
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = MagicMock()
    with patch("services.neon_sync_checker.psycopg2.connect", return_value=mock_conn):
        result = checker.update_pump_multiplier("Arabic", 2.5, user_id="yebyen")
    assert result is True


def test_update_pump_multiplier_calls_commit(checker):
    """conn.commit() is called exactly once after the UPDATE."""
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = MagicMock()
    with patch("services.neon_sync_checker.psycopg2.connect", return_value=mock_conn):
        checker.update_pump_multiplier("Arabic", 2.0, user_id="yebyen")
    mock_conn.commit.assert_called_once()


def test_update_pump_multiplier_language_uppercased(checker):
    """Lowercase language_name is uppercased in the SQL execute params."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    with patch("services.neon_sync_checker.psycopg2.connect", return_value=mock_conn):
        checker.update_pump_multiplier("arabic", 1.5, user_id="yebyen")
    args, _ = mock_cur.execute.call_args
    assert args[1][1] == "ARABIC"


def test_update_pump_multiplier_mixed_case_uppercased(checker):
    """Mixed-case language names are uppercased in the SQL execute params."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    with patch("services.neon_sync_checker.psycopg2.connect", return_value=mock_conn):
        checker.update_pump_multiplier("Greek", 3.0, user_id="yebyen")
    args, _ = mock_cur.execute.call_args
    assert args[1][1] == "GREEK"


def test_update_pump_multiplier_correct_params(checker):
    """multiplier and resolved user_id are in the correct SQL param positions."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    with patch("services.neon_sync_checker.psycopg2.connect", return_value=mock_conn):
        checker.update_pump_multiplier("Arabic", 2.0, user_id="yebyen")
    args, _ = mock_cur.execute.call_args
    params = args[1]
    assert params[0] == 2.0        # multiplier
    assert params[2] == FAKE_UUID  # resolved user_id


def test_update_pump_multiplier_connect_exception_returns_false(checker):
    """Returns False (does not raise) when psycopg2.connect raises."""
    with patch(
        "services.neon_sync_checker.psycopg2.connect",
        side_effect=Exception("connection refused"),
    ):
        result = checker.update_pump_multiplier("Arabic", 2.0, user_id="yebyen")
    assert result is False


def test_update_pump_multiplier_execute_exception_returns_false(checker):
    """Returns False when cursor.execute raises (partial transaction, no commit)."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.execute.side_effect = Exception("column not found")
    mock_conn.cursor.return_value = mock_cur
    with patch("services.neon_sync_checker.psycopg2.connect", return_value=mock_conn):
        result = checker.update_pump_multiplier("Arabic", 2.0, user_id="yebyen")
    assert result is False
