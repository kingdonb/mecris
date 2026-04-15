"""Unit tests for services/health_checker.py — HealthChecker class.

Covers:
- get_process_statuses: no URL, happy-path DB rows, None heartbeat, exception propagation
- get_system_health: no URL, healthy (any active), degraded (none active), exception fallback

Closes yebyen/mecris#189
"""
import os
import datetime
import pytest
from unittest.mock import patch, MagicMock
from services.health_checker import HealthChecker

FAKE_URL = "postgres://fake"
FAKE_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_conn_mock(rows):
    """Return (mock_conn, mock_cur) wired up as context managers with fetchall returning rows."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchall.return_value = rows
    return mock_conn, mock_cur


# ---------------------------------------------------------------------------
# get_process_statuses
# ---------------------------------------------------------------------------

class TestGetProcessStatuses:
    def test_no_url_returns_empty_list(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NEON_DB_URL", None)
            checker = HealthChecker()
            result = checker.get_process_statuses()
        assert result == []

    def test_with_url_maps_rows_correctly(self):
        ts = datetime.datetime(2026, 4, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)
        rows = [
            ("mcp-server", "pid-111", ts, True),
            ("spin-cloud", "pid-222", ts, False),
        ]
        mock_conn, _ = _make_conn_mock(rows)
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", return_value=mock_conn):
                checker = HealthChecker()
                result = checker.get_process_statuses(user_id=FAKE_UUID)

        assert len(result) == 2
        assert result[0]["role"] == "mcp-server"
        assert result[0]["process_id"] == "pid-111"
        assert result[0]["last_heartbeat"] == ts.isoformat()
        assert result[0]["is_active"] is True
        assert result[1]["role"] == "spin-cloud"
        assert result[1]["is_active"] is False

    def test_heartbeat_none_maps_to_none(self):
        rows = [("android-client", "pid-333", None, False)]
        mock_conn, _ = _make_conn_mock(rows)
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", return_value=mock_conn):
                checker = HealthChecker()
                result = checker.get_process_statuses()

        assert result[0]["last_heartbeat"] is None

    def test_db_exception_propagates(self):
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", side_effect=Exception("connection refused")):
                checker = HealthChecker()
                with pytest.raises(Exception, match="connection refused"):
                    checker.get_process_statuses()


# ---------------------------------------------------------------------------
# get_system_health
# ---------------------------------------------------------------------------

class TestGetSystemHealth:
    def test_no_url_returns_error_dict(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NEON_DB_URL", None)
            checker = HealthChecker()
            result = checker.get_system_health()

        assert "error" in result
        assert "NEON_DB_URL" in result["error"]
        assert result["processes"] == []
        assert "overall_status" not in result

    def test_any_active_returns_healthy(self):
        ts = datetime.datetime(2026, 4, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)
        rows = [
            ("mcp-server", "pid-111", ts, True),
            ("spin-cloud", "pid-222", ts, False),
        ]
        mock_conn, _ = _make_conn_mock(rows)
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", return_value=mock_conn):
                checker = HealthChecker()
                result = checker.get_system_health()

        assert result["overall_status"] == "healthy"
        assert len(result["processes"]) == 2

    def test_all_inactive_returns_degraded(self):
        ts = datetime.datetime(2026, 4, 15, 8, 0, 0, tzinfo=datetime.timezone.utc)
        rows = [
            ("mcp-server", "pid-111", ts, False),
            ("spin-cloud", "pid-222", ts, False),
        ]
        mock_conn, _ = _make_conn_mock(rows)
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", return_value=mock_conn):
                checker = HealthChecker()
                result = checker.get_system_health()

        assert result["overall_status"] == "degraded"

    def test_empty_process_list_returns_degraded(self):
        mock_conn, _ = _make_conn_mock([])
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", return_value=mock_conn):
                checker = HealthChecker()
                result = checker.get_system_health()

        assert result["overall_status"] == "degraded"
        assert result["processes"] == []

    def test_db_exception_returns_error_dict(self):
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", side_effect=Exception("neon timeout")):
                checker = HealthChecker()
                result = checker.get_system_health()

        assert "error" in result
        assert "neon timeout" in result["error"]
        assert result["processes"] == []
