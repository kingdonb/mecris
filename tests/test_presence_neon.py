"""
Tests for ghost.presence Neon-backed store — Phase 1 (kingdonb/mecris#164).

Covers:
- NeonPresenceStore.upsert — sets/updates presence record
- NeonPresenceStore.get — retrieves current record, None if missing
- NeonPresenceStore.set_pound_sand — human-triggered POUND_SAND transition
- NeonPresenceStore.escalate_to_sofy — bot emergency override (POUND_SAND → SOFY)
- get_neon_store — returns None when NEON_DB_URL unset or psycopg2 unavailable
- File-based lock API unchanged (existing tests: test_ghost_presence.py)
"""

import os
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from ghost.presence import (
    StatusType,
    PresenceRecord,
    NeonPresenceStore,
    get_neon_store,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_row(user_id="user1", status="pulse", source="cli"):
    """Return a DB row tuple matching (user_id, last_active, last_human, last_ghost, source, status_type)."""
    ts = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    return (user_id, ts, ts if status == "active_human" else None, ts if status == "active_ghost" else None, source, status)


def _mock_conn(fetchone_row):
    """Build context-manager-compatible mock psycopg2 connection."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = fetchone_row

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor

    return mock_conn, mock_cursor


# ---------------------------------------------------------------------------
# StatusType enum
# ---------------------------------------------------------------------------

class TestStatusTypeEnum:
    def test_all_values_present(self):
        values = {s.value for s in StatusType}
        assert values == {
            "pulse",
            "active_human",
            "active_ghost",
            "needs_attention",
            "pound_sand",
            "shits_on_fire_yo",
            "silent",
        }

    def test_round_trip_from_string(self):
        assert StatusType("pound_sand") == StatusType.POUND_SAND
        assert StatusType("shits_on_fire_yo") == StatusType.SHITS_ON_FIRE_YO


# ---------------------------------------------------------------------------
# NeonPresenceStore.upsert
# ---------------------------------------------------------------------------

class TestNeonPresenceStoreUpsert:
    def test_upsert_pulse_returns_record(self):
        row = _fake_row(status="pulse")
        mock_conn, _ = _mock_conn(row)

        with patch("ghost.presence.psycopg2.connect", return_value=mock_conn):
            store = NeonPresenceStore("postgresql://fake")
            record = store.upsert("user1", StatusType.PULSE)

        assert record.user_id == "user1"
        assert record.status_type == StatusType.PULSE
        assert record.source == "cli"

    def test_upsert_returns_presence_record_dataclass(self):
        row = _fake_row(status="active_human", source="web")
        mock_conn, _ = _mock_conn(row)

        with patch("ghost.presence.psycopg2.connect", return_value=mock_conn):
            store = NeonPresenceStore("postgresql://fake")
            record = store.upsert("user1", StatusType.ACTIVE_HUMAN, source="web")

        assert isinstance(record, PresenceRecord)
        assert record.status_type == StatusType.ACTIVE_HUMAN
        assert record.source == "web"

    def test_upsert_executes_insert_on_conflict_sql(self):
        row = _fake_row()
        mock_conn, mock_cursor = _mock_conn(row)

        with patch("ghost.presence.psycopg2.connect", return_value=mock_conn):
            store = NeonPresenceStore("postgresql://fake")
            store.upsert("user1", StatusType.PULSE)

        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO presence" in sql
        assert "ON CONFLICT" in sql
        assert "RETURNING" in sql

    def test_upsert_passes_correct_params(self):
        row = _fake_row(status="needs_attention", source="bot")
        mock_conn, mock_cursor = _mock_conn(row)

        with patch("ghost.presence.psycopg2.connect", return_value=mock_conn):
            store = NeonPresenceStore("postgresql://fake")
            store.upsert("user42", StatusType.NEEDS_ATTENTION, source="bot")

        params = mock_cursor.execute.call_args[0][1]
        assert params[0] == "user42"
        assert params[1] == "bot"
        assert params[2] == "needs_attention"


# ---------------------------------------------------------------------------
# NeonPresenceStore.get
# ---------------------------------------------------------------------------

class TestNeonPresenceStoreGet:
    def test_get_returns_record_when_exists(self):
        row = _fake_row(status="pound_sand")
        mock_conn, _ = _mock_conn(row)

        with patch("ghost.presence.psycopg2.connect", return_value=mock_conn):
            store = NeonPresenceStore("postgresql://fake")
            record = store.get("user1")

        assert record is not None
        assert record.status_type == StatusType.POUND_SAND

    def test_get_returns_none_when_no_record(self):
        mock_conn, _ = _mock_conn(None)

        with patch("ghost.presence.psycopg2.connect", return_value=mock_conn):
            store = NeonPresenceStore("postgresql://fake")
            record = store.get("nonexistent")

        assert record is None

    def test_get_preserves_last_active_timestamp(self):
        ts = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
        row = ("user1", ts, None, None, "cli", "pulse")
        mock_conn, _ = _mock_conn(row)

        with patch("ghost.presence.psycopg2.connect", return_value=mock_conn):
            store = NeonPresenceStore("postgresql://fake")
            record = store.get("user1")

        assert record.last_active == ts


# ---------------------------------------------------------------------------
# State machine: POUND_SAND and SOFY
# ---------------------------------------------------------------------------

class TestStateMachine:
    def test_set_pound_sand_sets_correct_status(self):
        row = _fake_row(status="pound_sand", source="cli")
        mock_conn, mock_cursor = _mock_conn(row)

        with patch("ghost.presence.psycopg2.connect", return_value=mock_conn):
            store = NeonPresenceStore("postgresql://fake")
            record = store.set_pound_sand("user1")

        assert record.status_type == StatusType.POUND_SAND
        params = mock_cursor.execute.call_args[0][1]
        assert "pound_sand" in params

    def test_escalate_to_sofy_overrides_pound_sand(self):
        """Bot emergency override must work even when current status is POUND_SAND."""
        row = _fake_row(status="shits_on_fire_yo", source="bot")
        mock_conn, mock_cursor = _mock_conn(row)

        with patch("ghost.presence.psycopg2.connect", return_value=mock_conn):
            store = NeonPresenceStore("postgresql://fake")
            record = store.escalate_to_sofy("user1")

        assert record.status_type == StatusType.SHITS_ON_FIRE_YO
        params = mock_cursor.execute.call_args[0][1]
        assert "shits_on_fire_yo" in params

    def test_escalate_to_sofy_uses_bot_source(self):
        """escalate_to_sofy records source='bot' to identify bot-originated emergencies."""
        row = _fake_row(status="shits_on_fire_yo", source="bot")
        mock_conn, mock_cursor = _mock_conn(row)

        with patch("ghost.presence.psycopg2.connect", return_value=mock_conn):
            store = NeonPresenceStore("postgresql://fake")
            store.escalate_to_sofy("user1")

        params = mock_cursor.execute.call_args[0][1]
        assert params[1] == "bot"  # source is second param

    def test_set_pound_sand_uses_cli_source_by_default(self):
        row = _fake_row(status="pound_sand", source="cli")
        mock_conn, mock_cursor = _mock_conn(row)

        with patch("ghost.presence.psycopg2.connect", return_value=mock_conn):
            store = NeonPresenceStore("postgresql://fake")
            store.set_pound_sand("user1")

        params = mock_cursor.execute.call_args[0][1]
        assert params[1] == "cli"


# ---------------------------------------------------------------------------
# get_neon_store convenience function
# ---------------------------------------------------------------------------

class TestGetNeonStore:
    def test_returns_none_when_no_env_and_no_arg(self):
        env_without_neon = {k: v for k, v in os.environ.items() if k != "NEON_DB_URL"}
        with patch.dict(os.environ, env_without_neon, clear=True):
            store = get_neon_store()
        assert store is None

    def test_returns_store_when_url_provided_directly(self):
        store = get_neon_store("postgresql://fake")
        assert isinstance(store, NeonPresenceStore)
        assert store.neon_url == "postgresql://fake"

    def test_returns_store_when_neon_db_url_set(self):
        with patch.dict(os.environ, {"NEON_DB_URL": "postgresql://from-env"}):
            store = get_neon_store()
        assert store is not None
        assert store.neon_url == "postgresql://from-env"

    def test_returns_none_when_psycopg2_unavailable(self):
        with patch("ghost.presence._PSYCOPG2_AVAILABLE", False):
            store = get_neon_store("postgresql://fake")
        assert store is None
