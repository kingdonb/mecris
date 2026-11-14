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


# ---------------------------------------------------------------------------
# Beeminder graph of plan usage (kingdonb/mecris#371)
# ---------------------------------------------------------------------------

NEXT_MON_4AM_ET = "2026-11-23T04:00:00-05:00"


def _hist(*rows):
    """rows: (id, weekly_pct, weekly_reset) -> readings as the store returns them."""
    return [{**_reading(pct, weekly_reset=reset), "id": rid} for rid, pct, reset in rows]


class TestCumulativeWeeklyPct:
    def test_empty_history_is_zero(self):
        assert cpu.cumulative_weekly_pct([]) == 0

    def test_one_week_counts_its_highest_reading(self):
        h = _hist((1, 10, MON_4AM_ET), (2, 62, MON_4AM_ET), (3, 40, MON_4AM_ET))
        assert cpu.cumulative_weekly_pct(h) == 62

    def test_weeks_add_up_across_the_reset(self):
        h = _hist((1, 62, MON_4AM_ET), (2, 3, NEXT_MON_4AM_ET))
        assert cpu.cumulative_weekly_pct(h) == 65

    def test_same_week_with_slightly_different_reset_time_is_one_week(self):
        h = _hist((1, 20, MON_4AM_ET), (2, 30, "2026-11-16T04:01:00-05:00"))
        assert cpu.cumulative_weekly_pct(h) == 30

    def test_order_does_not_matter(self):
        h = _hist((2, 3, NEXT_MON_4AM_ET), (1, 62, MON_4AM_ET))
        assert cpu.cumulative_weekly_pct(h) == 65

    def test_reading_without_weekly_window_is_ignored(self):
        broken = {"id": 9, "windows": [{"kind": "session", "pct_used": 50, "resets_at": TONIGHT_8PM_ET}]}
        assert cpu.cumulative_weekly_pct(_hist((1, 10, MON_4AM_ET)) + [broken]) == 10


class TestBeeminderDatapoint:
    def test_first_reading_pushes_its_value(self):
        dp = cpu.beeminder_datapoint(_hist((7, 12, MON_4AM_ET)), reading_id=7)
        assert dp["value"] == 12
        assert dp["requestid"] == "claude-plan-7"
        assert "12% of this week" in dp["comment"] and "ultra" in dp["comment"]

    def test_unchanged_total_is_not_pushed(self):
        h = _hist((1, 62, MON_4AM_ET), (2, 62, MON_4AM_ET))
        assert cpu.beeminder_datapoint(h, reading_id=2) is None

    def test_lower_correction_in_same_week_is_not_pushed(self):
        h = _hist((1, 62, MON_4AM_ET), (2, 50, MON_4AM_ET))
        assert cpu.beeminder_datapoint(h, reading_id=2) is None

    def test_new_week_keeps_the_line_climbing(self):
        h = _hist((1, 62, MON_4AM_ET), (2, 3, NEXT_MON_4AM_ET))
        dp = cpu.beeminder_datapoint(h, reading_id=2)
        assert dp["value"] == 65  # never drops at the weekly reset
        assert "3% of this week" in dp["comment"]

    def test_requestid_is_stable_for_the_same_reading(self):
        h = _hist((1, 10, MON_4AM_ET), (2, 20, MON_4AM_ET))
        assert cpu.beeminder_datapoint(h, 2)["requestid"] == cpu.beeminder_datapoint(list(reversed(h)), 2)["requestid"]

    def test_unknown_reading_id_is_not_pushed(self):
        assert cpu.beeminder_datapoint(_hist((1, 10, MON_4AM_ET)), reading_id=99) is None


class _FakeBeeminder:
    def __init__(self, error=None):
        self.calls, self.error = [], error

    async def add_datapoint(self, goal_slug, value, comment="", requestid=None, daystamp=None):
        self.calls.append((goal_slug, value, comment, requestid))
        if self.error:
            raise self.error
        return True


class _ApiError(Exception):
    def __init__(self, status_code):
        super().__init__("Beeminder API call failed: body with details")
        self.status_code = status_code


class TestSyncReadingToBeeminder:
    @pytest.mark.asyncio
    async def test_no_goal_configured_makes_no_call(self):
        client = _FakeBeeminder()
        out = await cpu.sync_reading_to_beeminder(client, None, _hist((1, 10, MON_4AM_ET)), 1)
        assert out["pushed"] is False and client.calls == []
        assert "CLAUDE_BEEMINDER_GOAL" in out["reason"]

    @pytest.mark.asyncio
    async def test_pushes_changed_total(self):
        client = _FakeBeeminder()
        out = await cpu.sync_reading_to_beeminder(client, "claude-usage", _hist((1, 10, MON_4AM_ET)), 1)
        assert out == {"pushed": True, "goal": "claude-usage", "value": 10, "requestid": "claude-plan-1"}
        assert client.calls[0][:2] == ("claude-usage", 10) and client.calls[0][3] == "claude-plan-1"

    @pytest.mark.asyncio
    async def test_unchanged_total_makes_no_call(self):
        client = _FakeBeeminder()
        h = _hist((1, 10, MON_4AM_ET), (2, 10, MON_4AM_ET))
        out = await cpu.sync_reading_to_beeminder(client, "claude-usage", h, 2)
        assert out["pushed"] is False and client.calls == []

    @pytest.mark.asyncio
    async def test_duplicate_requestid_counts_as_already_in(self):
        client = _FakeBeeminder(error=_ApiError(422))
        out = await cpu.sync_reading_to_beeminder(client, "claude-usage", _hist((1, 10, MON_4AM_ET)), 1)
        assert out["pushed"] is True and out["note"] == "already recorded"

    @pytest.mark.asyncio
    async def test_failure_is_reported_not_raised_and_carries_no_response_text(self):
        client = _FakeBeeminder(error=_ApiError(500))
        out = await cpu.sync_reading_to_beeminder(client, "claude-usage", _hist((1, 10, MON_4AM_ET)), 1)
        assert out["pushed"] is False
        assert out["error"] == "_ApiError status=500"
        assert "details" not in str(out)
