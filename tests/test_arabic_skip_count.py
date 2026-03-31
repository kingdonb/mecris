"""
Tests for services/arabic_skip_counter.py

Verifies that count_arabic_reminders:
  - returns an int in all cases
  - returns the count from the DB on success
  - returns 0 on DB error (fail-safe)
  - queries both arabic reminder type strings
"""

import sys
import pytest
from unittest.mock import MagicMock, patch

from services.arabic_skip_counter import count_arabic_reminders


def _make_psycopg2_mock(count: int):
    """Build a minimal psycopg2 mock returning `count` from fetchone."""
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (count,)
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)

    mock_psycopg2 = MagicMock()
    mock_psycopg2.connect.return_value = mock_conn
    return mock_psycopg2, mock_cur


def test_returns_int_zero_when_no_rows():
    """Returns 0 (as int) when no arabic reminders are in the window."""
    mock_pg, _ = _make_psycopg2_mock(0)
    with patch.dict(sys.modules, {"psycopg2": mock_pg}):
        result = count_arabic_reminders("postgresql://test", "user1")
    assert isinstance(result, int)
    assert result == 0


def test_returns_correct_count():
    """Returns the row count from the DB as an int."""
    mock_pg, _ = _make_psycopg2_mock(3)
    with patch.dict(sys.modules, {"psycopg2": mock_pg}):
        result = count_arabic_reminders("postgresql://test", "user1")
    assert isinstance(result, int)
    assert result == 3


def test_returns_zero_on_db_error():
    """Returns 0 (fail-safe) when the DB connection raises an exception."""
    mock_pg = MagicMock()
    mock_pg.connect.side_effect = Exception("connection refused")
    with patch.dict(sys.modules, {"psycopg2": mock_pg}):
        result = count_arabic_reminders("postgresql://test", "user1")
    assert isinstance(result, int)
    assert result == 0


def test_queries_correct_reminder_types():
    """SQL is called with both arabic_review_reminder and arabic_review_escalation."""
    mock_pg, mock_cur = _make_psycopg2_mock(5)
    with patch.dict(sys.modules, {"psycopg2": mock_pg}):
        count_arabic_reminders("postgresql://test", "user1", hours=12)

    call_args = mock_cur.execute.call_args
    params = call_args[0][1]  # (sql, params) positional args
    assert "arabic_review_reminder" in params[0]
    assert "arabic_review_escalation" in params[0]
    assert params[1] == "user1"
