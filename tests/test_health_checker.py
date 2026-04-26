"""Unit tests for services/health_checker.py — HealthChecker class.

Covers:
- get_process_statuses: no URL, happy-path DB rows, None heartbeat, exception propagation
- get_process_statuses: with observability columns (last_status, last_error, intent)
- get_process_statuses: pre-migration fallback (columns absent)
- get_system_health: no URL, healthy (any active), degraded (none active), exception fallback

Closes yebyen/mecris#189
Updated: yebyen/mecris#282 (Observability Mandate Phase 1 — add last_status/last_error/intent)
"""
import os
import datetime
import pytest
from unittest.mock import patch, MagicMock, call
from services.health_checker import HealthChecker

FAKE_URL = "postgres://fake"
FAKE_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

# Column rows returned by the information_schema check when migration v8 is applied
_OBS_COL_ROWS = [("last_status",), ("last_error",), ("intent",)]
# Column rows returned when migration v8 has NOT been applied
_NO_OBS_COL_ROWS = []


def _make_conn_mock(data_rows, obs_cols_present: bool = False):
    """Return (mock_conn, mock_cur) wired up for the two-query pattern in HealthChecker.

    First fetchall(): returns column check rows (obs_cols_present controls this).
    Second fetchall(): returns data_rows.
    """
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    col_rows = _OBS_COL_ROWS if obs_cols_present else _NO_OBS_COL_ROWS
    mock_cur.fetchall.side_effect = [col_rows, data_rows]
    return mock_conn, mock_cur


# ---------------------------------------------------------------------------
# get_process_statuses — pre-migration (no observability columns)
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
        mock_conn, _ = _make_conn_mock(rows, obs_cols_present=False)
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

    def test_pre_migration_obs_fields_are_none(self):
        """Without migration v8, last_status/last_error/intent must still be present but None."""
        ts = datetime.datetime(2026, 4, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)
        rows = [("mcp-server", "pid-111", ts, True)]
        mock_conn, _ = _make_conn_mock(rows, obs_cols_present=False)
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", return_value=mock_conn):
                checker = HealthChecker()
                result = checker.get_process_statuses()

        assert result[0]["last_status"] is None
        assert result[0]["last_error"] is None
        assert result[0]["intent"] is None

    def test_heartbeat_none_maps_to_none(self):
        rows = [("android-client", "pid-333", None, False)]
        mock_conn, _ = _make_conn_mock(rows, obs_cols_present=False)
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
# get_process_statuses — post-migration (observability columns present)
# ---------------------------------------------------------------------------

class TestGetProcessStatusesWithObsColumns:
    def test_obs_columns_returned(self):
        ts = datetime.datetime(2026, 4, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)
        rows = [
            ("leader", "pid-abc", ts, True, "Heartbeat active", None, "maintain leadership"),
            ("android_client", "pid-xyz", ts, False, None, "timeout", None),
        ]
        mock_conn, _ = _make_conn_mock(rows, obs_cols_present=True)
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", return_value=mock_conn):
                checker = HealthChecker()
                result = checker.get_process_statuses()

        assert result[0]["last_status"] == "Heartbeat active"
        assert result[0]["last_error"] is None
        assert result[0]["intent"] == "maintain leadership"
        assert result[1]["last_status"] is None
        assert result[1]["last_error"] == "timeout"
        assert result[1]["intent"] is None

    def test_obs_columns_all_fields_present(self):
        """All 7 expected fields are in every result dict when obs columns present."""
        ts = datetime.datetime(2026, 4, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)
        rows = [("leader", "pid-abc", ts, True, "Elected as leader", None, "claim leadership")]
        mock_conn, _ = _make_conn_mock(rows, obs_cols_present=True)
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", return_value=mock_conn):
                checker = HealthChecker()
                result = checker.get_process_statuses()

        for field in ("role", "process_id", "last_heartbeat", "is_active",
                      "last_status", "last_error", "intent"):
            assert field in result[0], f"Missing field '{field}'"

    def test_obs_columns_heartbeat_isoformat(self):
        ts = datetime.datetime(2026, 4, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)
        rows = [("leader", "pid-abc", ts, True, "Heartbeat active", None, "maintain leadership")]
        mock_conn, _ = _make_conn_mock(rows, obs_cols_present=True)
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", return_value=mock_conn):
                checker = HealthChecker()
                result = checker.get_process_statuses()

        assert result[0]["last_heartbeat"] == ts.isoformat()


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
        mock_conn, _ = _make_conn_mock(rows, obs_cols_present=False)
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
        mock_conn, _ = _make_conn_mock(rows, obs_cols_present=False)
        with patch.dict(os.environ, {"NEON_DB_URL": FAKE_URL}):
            with patch("psycopg2.connect", return_value=mock_conn):
                checker = HealthChecker()
                result = checker.get_system_health()

        assert result["overall_status"] == "degraded"

    def test_empty_process_list_returns_degraded(self):
        mock_conn, mock_cur = MagicMock(), MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.side_effect = [_NO_OBS_COL_ROWS, []]

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
