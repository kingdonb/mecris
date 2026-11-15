"""Tests for fetch_system_pulse() Bus Standardization — kingdonb/mecris#245, yebyen/mecris#337.

Covers:
- Modalities include last_status/intent/last_error when DB columns return values
- Fields default to None when columns are NULL (pre-migration or unset)
- Empty result set returns {"modalities": []}
- unknown_cloud role is skipped
- Display name mapping for known roles
- No NEON_DB_URL → returns empty modalities
"""

import sys
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

_FAKE_HB = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)


def _make_conn_mock(rows):
    """Build a psycopg2 connection mock returning rows from fetchall."""
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchall.return_value = rows

    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    return conn, cur


def _base_patches(conn):
    env_patch = patch.dict(
        "os.environ",
        {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"},
    )
    db_patch = patch("psycopg2.connect", return_value=conn)
    return env_patch, db_patch


@pytest.mark.asyncio
async def test_obs_fields_included_when_present():
    """Modalities include last_status/intent/last_error when DB columns return values."""
    sys.modules.pop("mcp_server", None)
    rows = [("leader", _FAKE_HB, 2.0, "Heartbeat active", "maintain leadership", None)]
    conn, _ = _make_conn_mock(rows)
    env_patch, db_patch = _base_patches(conn)

    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            result = await fetch_system_pulse("test-user")

    assert len(result["modalities"]) == 1
    mod = result["modalities"][0]
    assert mod["last_status"] == "Heartbeat active"
    assert mod["intent"] == "maintain leadership"
    assert mod["last_error"] is None


@pytest.mark.asyncio
async def test_obs_fields_none_when_null():
    """Fields default to None when columns are NULL (pre-migration or not yet written)."""
    sys.modules.pop("mcp_server", None)
    rows = [("leader", _FAKE_HB, 1.5, None, None, None)]
    conn, _ = _make_conn_mock(rows)
    env_patch, db_patch = _base_patches(conn)

    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            result = await fetch_system_pulse("test-user")

    assert len(result["modalities"]) == 1
    mod = result["modalities"][0]
    assert mod["last_status"] is None
    assert mod["intent"] is None
    assert mod["last_error"] is None


@pytest.mark.asyncio
async def test_empty_result_returns_empty_modalities():
    """Empty result set returns {"modalities": []}."""
    sys.modules.pop("mcp_server", None)
    conn, _ = _make_conn_mock([])
    env_patch, db_patch = _base_patches(conn)

    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            result = await fetch_system_pulse("test-user")

    assert result == {"modalities": []}


@pytest.mark.asyncio
async def test_unknown_cloud_role_skipped():
    """unknown_cloud rows are excluded from modalities."""
    sys.modules.pop("mcp_server", None)
    rows = [
        ("unknown_cloud", _FAKE_HB, 5.0, None, None, None),
        ("leader", _FAKE_HB, 2.0, "Heartbeat active", "maintain leadership", None),
    ]
    conn, _ = _make_conn_mock(rows)
    env_patch, db_patch = _base_patches(conn)

    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            result = await fetch_system_pulse("test-user")

    assert len(result["modalities"]) == 1
    assert result["modalities"][0]["role"] == "MCP SERVER"


@pytest.mark.asyncio
async def test_display_name_mapping():
    """Known roles are mapped to human-friendly display names."""
    sys.modules.pop("mcp_server", None)
    rows = [
        ("akamai_functions", _FAKE_HB, 3.0, None, None, None),
        ("fermyon_cloud", _FAKE_HB, 4.0, None, None, None),
        ("android_client", _FAKE_HB, 5.0, None, None, None),
    ]
    conn, _ = _make_conn_mock(rows)
    env_patch, db_patch = _base_patches(conn)

    with env_patch, db_patch:
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            result = await fetch_system_pulse("test-user")

    roles = [m["role"] for m in result["modalities"]]
    assert "AKAMAI FUNCTIONS" in roles
    assert "FERMYON CLOUD" not in roles  # retired (#346)
    assert "ANDROID CLIENT" in roles


@pytest.mark.asyncio
async def test_no_neon_url_returns_empty():
    """Returns empty modalities when NEON_DB_URL is not set at call time."""
    sys.modules.pop("mcp_server", None)

    # Import with NEON_DB_URL so mcp_server module-level init succeeds,
    # then call the function without NEON_DB_URL to exercise the early-return guard.
    with patch.dict("os.environ", {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}):
        with patch("psycopg2.connect"):
            from mcp_server import fetch_system_pulse

    with patch.dict("os.environ", {}, clear=True):
        result = await fetch_system_pulse("test-user")

    assert result == {"modalities": []}


# ---------------------------------------------------------------------------
# Role registry from contracts/pulse_roles.json (#346)
# ---------------------------------------------------------------------------

import json
import os
from pathlib import Path

_PULSE = json.loads((Path(__file__).resolve().parents[1] / "contracts" / "pulse_roles.json").read_text())
_ENV = {"NEON_DB_URL": "postgres://fake", "DEFAULT_USER_ID": "test-user"}


async def _pulse(rows, ghost=None, refusals=None):
    """Run fetch_system_pulse over rows; refusals is the (total, bad_key) row or None."""
    sys.modules.pop("mcp_server", None)
    conn, cur = _make_conn_mock(rows)
    cur.fetchone.return_value = refusals
    with patch.dict("os.environ", _ENV), patch("psycopg2.connect", return_value=conn):
        os.environ.pop("MECRIS_GHOST_ENABLED", None)
        if ghost is not None:
            os.environ["MECRIS_GHOST_ENABLED"] = ghost
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            return await fetch_system_pulse("test-user")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _PULSE["cases"], ids=lambda c: f"{c['role']}-{c['minutes']}")
async def test_contract_role_cases(case):
    result = await _pulse([(case["role"], _FAKE_HB, float(case["minutes"]), None, None, None)])
    mods = result["modalities"]
    if not case["expect"]["visible"]:
        assert mods == []
        return
    assert len(mods) == 1
    assert mods[0]["role"] == case["expect"]["display"]
    assert mods[0]["status"] == case["expect"]["status"]
    assert mods[0]["minutes_since"] == case["minutes"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _PULSE["duplicate_cases"], ids=lambda c: c["name"])
async def test_contract_duplicate_cases(case):
    # The own flag is the seventh column; last_error marks which row won.
    rows = [(r["role"], _FAKE_HB, float(r["minutes"]), None, None, "own" if r["own"] else "global", r["own"])
            for r in case["rows"]]
    result = await _pulse(rows)
    got = [{"display": m["role"], "status": m["status"], "own": m["last_error"] == "own",
            "minutes": m["minutes_since"]} for m in result["modalities"]]
    assert got == case["expect"]


@pytest.mark.asyncio
async def test_android_at_42_minutes_is_healthy():
    result = await _pulse([("android_client", _FAKE_HB, 42.0, None, None, None)])
    assert result["modalities"][0]["status"] == "healthy"


@pytest.mark.asyncio
async def test_minutes_are_floored_not_rounded():
    result = await _pulse([("android_client", _FAKE_HB, 89.99, None, None, None)])
    assert result["modalities"][0]["minutes_since"] == 89
    assert result["modalities"][0]["status"] == "healthy"


@pytest.mark.asyncio
async def test_retired_and_stale_unknown_rows_are_hidden_fresh_unknown_shown():
    rows = [
        ("fermyon_cloud", _FAKE_HB, 1.0, None, None, None),
        ("unknown_cloud", _FAKE_HB, 1.0, None, None, None),
        ("unknown", _FAKE_HB, 190000.0, None, None, None),
        ("some_new_role", _FAKE_HB, 10.0, None, None, None),
    ]
    result = await _pulse(rows)
    assert [(m["role"], m["status"]) for m in result["modalities"]] == [("SOME NEW ROLE", "unknown")]


@pytest.mark.asyncio
async def test_ghost_is_paused_once_while_flag_unset():
    rows = [
        ("active_ghost", _FAKE_HB, 98000.0, None, None, None, True),
        ("active_ghost", _FAKE_HB, 99000.0, None, None, None, False),
    ]
    result = await _pulse(rows)
    assert [(m["role"], m["status"]) for m in result["modalities"]] == [("GHOST", "paused")]


@pytest.mark.asyncio
async def test_ghost_gets_a_timed_status_when_enabled():
    result = await _pulse([("active_ghost", _FAKE_HB, 30.0, None, None, None)], ghost="true")
    assert [(m["role"], m["status"]) for m in result["modalities"]] == [("GHOST", "healthy")]


@pytest.mark.asyncio
async def test_akamai_carries_refusals_today():
    result = await _pulse([("akamai_functions", _FAKE_HB, 30.0, "ok", "cron", None)], refusals=(4, 1))
    akamai = result["modalities"][0]
    assert akamai["refusals_today"] == 4
    assert akamai["bad_key_refusals_today"] == 1


@pytest.mark.asyncio
async def test_missing_refusal_table_counts_as_zero():
    sys.modules.pop("mcp_server", None)
    conn, cur = _make_conn_mock([("akamai_functions", _FAKE_HB, 30.0, None, None, None)])

    def execute(sql, *args, **kwargs):
        if "internal_refusals" in sql:
            raise Exception('relation "internal_refusals" does not exist')

    cur.execute.side_effect = execute
    with patch.dict("os.environ", _ENV), patch("psycopg2.connect", return_value=conn):
        with patch("mcp_server.usage_tracker") as mock_tracker:
            mock_tracker.resolve_user_id.return_value = "test-user"
            from mcp_server import fetch_system_pulse
            result = await fetch_system_pulse("test-user")
    akamai = result["modalities"][0]
    assert akamai["role"] == "AKAMAI FUNCTIONS"
    assert akamai["refusals_today"] == 0
    assert akamai["bad_key_refusals_today"] == 0


def test_refusals_count_the_new_york_day_and_flag_bad_key_only():
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", _ENV), patch("psycopg2.connect"):
        import mcp_server
    sql = mcp_server.REFUSALS_TODAY_SQL
    assert "America/New_York" in sql
    assert "'bad_key'" in sql
    assert "burned_key" not in sql


# ---------------------------------------------------------------------------
# Retired Fermyon endpoints (#346)
# ---------------------------------------------------------------------------

def test_server_no_longer_calls_fermyon():
    source = (Path(__file__).resolve().parents[1] / "mcp_server.py").read_text()
    assert "fermyon.app" not in source


def test_budget_governor_status_makes_no_network_call():
    sys.modules.pop("mcp_server", None)
    with patch.dict("os.environ", _ENV), patch("psycopg2.connect"):
        import mcp_server
        local = {"buckets": {}, "source": "neon"}
        with patch("httpx.post") as post, patch("httpx.Client") as client, \
             patch.object(mcp_server._neon_budget_governor, "get_status", return_value=local):
            result = mcp_server.get_budget_governor_status()
    post.assert_not_called()
    client.assert_not_called()
    assert result == local
