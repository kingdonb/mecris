"""Tests for HealthChecker service (kingdonb/mecris#97 — unified heartbeat + health visibility)."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from services.health_checker import HealthChecker


def _make_heartbeat(seconds_ago: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)


@pytest.fixture
def mock_neon_env():
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake"}):
        yield


def test_get_system_health_all_active(mock_neon_env):
    """Returns healthy when all processes have recent heartbeats."""
    recent = _make_heartbeat(30)

    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            ("android_client", "pid-xyz", recent, True),
            ("mcp_server", "pid-abc", recent, True),
        ]

        checker = HealthChecker()
        result = checker.get_system_health(user_id=None)

    assert result["overall_status"] == "healthy"
    assert len(result["processes"]) == 2
    roles = {p["role"] for p in result["processes"]}
    assert roles == {"mcp_server", "android_client"}
    assert all(p["is_active"] for p in result["processes"])


def test_get_system_health_stale_process(mock_neon_env):
    """Returns degraded when all heartbeats are stale."""
    stale = _make_heartbeat(300)

    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            ("mcp_server", "pid-abc", stale, False),
        ]

        checker = HealthChecker()
        result = checker.get_system_health(user_id=None)

    assert result["overall_status"] == "degraded"
    assert result["processes"][0]["is_active"] is False


def test_get_system_health_no_neon_url():
    """Returns error dict when NEON_DB_URL is not set."""
    import os
    with patch.dict("os.environ", {}, clear=True):
        os.environ.pop("NEON_DB_URL", None)
        checker = HealthChecker()
        result = checker.get_system_health(user_id=None)

    assert "error" in result
    assert result["processes"] == []


def test_get_system_health_db_error(mock_neon_env):
    """Returns error dict when DB query fails; does not raise."""
    with patch("psycopg2.connect", side_effect=Exception("connection refused")):
        checker = HealthChecker()
        result = checker.get_system_health(user_id=None)

    assert "error" in result
    assert "connection refused" in result["error"]
    assert result["processes"] == []


def test_get_system_health_heartbeat_serialized(mock_neon_env):
    """last_heartbeat is serialized to an ISO string, not left as a datetime."""
    ts = datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc)

    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            ("spin_failover", "pid-spin", ts, True),
        ]

        checker = HealthChecker()
        result = checker.get_system_health(user_id=None)

    p = result["processes"][0]
    assert p["last_heartbeat"] == ts.isoformat()
    assert isinstance(p["last_heartbeat"], str)


def test_get_system_health_mixed_active(mock_neon_env):
    """overall_status is healthy if at least one process is active."""
    recent = _make_heartbeat(30)
    stale = _make_heartbeat(300)

    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            ("android_client", "pid-xyz", stale, False),
            ("mcp_server", "pid-abc", recent, True),
        ]

        checker = HealthChecker()
        result = checker.get_system_health(user_id=None)

    assert result["overall_status"] == "healthy"
    active = [p for p in result["processes"] if p["is_active"]]
    inactive = [p for p in result["processes"] if not p["is_active"]]
    assert len(active) == 1
    assert len(inactive) == 1
