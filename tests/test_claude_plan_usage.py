"""Tests for Claude plan usage telemetry (kingdonb/mecris#344)."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

import claude_plan_usage as cpu

NOW = datetime(2026, 11, 13, 20, 0, tzinfo=timezone.utc)  # Fri 3 PM ET
MON_4AM_ET = "2026-11-16T04:00:00-05:00"
TONIGHT_8PM_ET = "2026-11-13T20:00:00-05:00"  # 01:00 UTC Sat


def _reading(weekly=62.0, fable=None, session=None, observed=NOW, weekly_reset=MON_4AM_ET):
    windows = cpu.build_windows(
        weekly, weekly_reset,
        fable, MON_4AM_ET if fable is not None else None,
        session, TONIGHT_8PM_ET if session is not None else None,
    )
    return cpu.make_reading(windows, observed_at=observed.isoformat())


class TestBuildWindows:
    def test_requires_a_window(self):
        with pytest.raises(ValueError):
            cpu.build_windows()

    def test_pct_out_of_range(self):
        with pytest.raises(ValueError):
            cpu.build_windows(120, MON_4AM_ET)

    def test_reset_required_with_pct(self):
        with pytest.raises(ValueError):
            cpu.build_windows(50, None)

    def test_omits_windows_without_pct(self):
        windows = cpu.build_windows(10, MON_4AM_ET)
        assert [w["kind"] for w in windows] == ["weekly_all"]

    def test_naive_reset_is_utc(self):
        windows = cpu.build_windows(10, "2026-11-16T09:00:00")
        assert windows[0]["resets_at"] == "2026-11-16T09:00:00+00:00"


class TestVerified:
    def test_session_window_means_unverified(self):
        assert _reading(session=20)["verified"] is False

    def test_no_session_window_unknown_unless_explicit(self):
        assert _reading()["verified"] is None

    def test_explicit_flag_wins(self):
        windows = cpu.build_windows(10, MON_4AM_ET)
        assert cpu.make_reading(windows, verified=True)["verified"] is True

    def test_bad_source_rejected(self):
        with pytest.raises(ValueError):
            cpu.make_reading(cpu.build_windows(10, MON_4AM_ET), source="cookie_jar")


class TestDeriveState:
    def test_no_reading_is_unknown(self):
        assert cpu.derive_state(None, NOW)["state"] == "unknown"

    def test_available(self):
        assert cpu.derive_state(_reading(62), NOW)["state"] == "available"

    def test_constrained_above_80(self):
        assert cpu.derive_state(_reading(81), NOW)["state"] == "constrained"

    def test_exactly_80_is_available(self):
        assert cpu.derive_state(_reading(80), NOW)["state"] == "available"

    def test_exhausted_at_100(self):
        assert cpu.derive_state(_reading(100), NOW)["state"] == "exhausted"

    def test_fable_window_can_bind(self):
        d = cpu.derive_state(_reading(30, fable=95), NOW)
        assert d["state"] == "constrained"
        assert d["binding_window"]["kind"] == "weekly_fable"

    def test_session_window_counts_while_fresh(self):
        assert cpu.derive_state(_reading(30, session=100), NOW)["state"] == "exhausted"

    def test_expired_session_window_is_dropped_not_trusted(self):
        later = NOW + timedelta(hours=6)  # after tonight's 8 PM ET session reset
        d = cpu.derive_state(_reading(30, session=100), later)
        assert d["state"] == "available"
        assert all(w["kind"] != "session" for w in d["fresh_windows"])

    def test_weekly_reset_passed_is_unknown(self):
        r = _reading(99, weekly_reset="2026-11-13T19:00:00+00:00")
        assert cpu.derive_state(r, NOW)["state"] == "unknown"

    def test_old_reading_is_stale(self):
        r = _reading(10, observed=NOW - timedelta(hours=25))
        d = cpu.derive_state(r, NOW)
        assert d["state"] == "unknown" and d["stale"] is True

    def test_verification_session_window_disappearing(self):
        unverified = _reading(40, session=50)
        verified = _reading(40)
        assert cpu.derive_state(unverified, NOW)["state"] == "available"
        assert cpu.derive_state(verified, NOW)["state"] == "available"


class TestSummarize:
    def test_available_line(self):
        s = cpu.summarize(_reading(62), NOW)
        assert s["summary_line"] == "Claude: available (62% weekly, resets Mon 4:00 AM)"

    def test_constrained_names_binding_window(self):
        s = cpu.summarize(_reading(30, fable=90), NOW)
        assert "weekly_fable 90%" in s["summary_line"]

    def test_unknown_without_reading(self):
        s = cpu.summarize(None, NOW)
        assert s["state"] == "unknown"
        assert s["summary_line"].startswith("Claude: unknown")
        assert s["observed_at"] is None


class TestStore:
    def test_no_db_does_not_record(self):
        store = cpu.ClaudePlanUsageStore.__new__(cpu.ClaudePlanUsageStore)
        store.neon_url, store._initialized = None, False
        assert store.record("u", _reading())["recorded"] is False
        assert store.latest("u") is None

    def test_record_and_latest_roundtrip(self):
        store = cpu.ClaudePlanUsageStore("postgres://fake")
        store._initialized = True
        reading = _reading(55)
        cur = MagicMock()
        cur.fetchone.side_effect = [
            (7,),
            ("ultra", None, json.dumps(reading["windows"]), "manual", NOW, ""),
        ]
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cur
        with patch("psycopg2.connect", return_value=conn):
            assert store.record("user-1", reading) == {"recorded": True, "id": 7}
            insert_args = cur.execute.call_args_list[0][0][1]
            assert insert_args[0] == "user-1"
            latest = store.latest("user-1")
            select_args = cur.execute.call_args_list[1][0][1]
            assert select_args == ("user-1",)
        assert latest["windows"] == reading["windows"]
        assert latest["observed_at"] == NOW.isoformat()
