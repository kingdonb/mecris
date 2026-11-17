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


class TestBeeminderDatapoints:
    """An odometer goal: the week's percentage goes in as it is, and a 0 @TARE
    datapoint at the weekly reset tells Beeminder the odometer started over (#390)."""

    def test_first_reading_ever_is_pushed_raw_with_no_tare(self):
        dps = cpu.beeminder_datapoints(_hist((7, 12, MON_4AM_ET)), reading_id=7)
        assert len(dps) == 1
        assert dps[0]["value"] == 12
        assert dps[0]["requestid"] == "claude-plan-7"
        assert "12% of this week" in dps[0]["comment"] and "ultra" in dps[0]["comment"]
        assert "running total" not in dps[0]["comment"]
        assert "timestamp" not in dps[0]

    def test_higher_reading_in_the_same_week_is_pushed_raw(self):
        dps = cpu.beeminder_datapoints(_hist((1, 10, MON_4AM_ET), (2, 20, MON_4AM_ET)), reading_id=2)
        assert [d["value"] for d in dps] == [20]

    def test_unchanged_reading_is_not_pushed(self):
        h = _hist((1, 62, MON_4AM_ET), (2, 62, MON_4AM_ET))
        assert cpu.beeminder_datapoints(h, reading_id=2) == []

    def test_lower_correction_in_same_week_is_not_pushed(self):
        h = _hist((1, 62, MON_4AM_ET), (2, 50, MON_4AM_ET))
        assert cpu.beeminder_datapoints(h, reading_id=2) == []

    def test_new_week_sends_a_tare_then_the_raw_reading(self):
        h = _hist((1, 62, MON_4AM_ET), (2, 3, NEXT_MON_4AM_ET))
        tare, reading = cpu.beeminder_datapoints(h, reading_id=2)
        assert tare["value"] == 0
        assert "@TARE" in tare["comment"]
        assert tare["requestid"] == "claude-tare-2026-11-16"
        # Dated at the reset itself (Mon 4:00 AM ET), however late the first reading comes.
        assert tare["timestamp"] == int(datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc).timestamp())
        assert reading["value"] == 3  # not 65: no running total
        assert reading["requestid"] == "claude-plan-2"
        assert "3% of this week" in reading["comment"]

    def test_later_readings_of_the_week_repeat_the_same_tare(self):
        """The tare goes with every push of the week. Its request id makes the
        repeats no-ops, and a tare that failed the first time gets another chance."""
        h = _hist((1, 62, MON_4AM_ET), (2, 3, NEXT_MON_4AM_ET), (3, 9, NEXT_MON_4AM_ET))
        tare, reading = cpu.beeminder_datapoints(h, reading_id=3)
        assert tare["requestid"] == "claude-tare-2026-11-16" and tare["value"] == 0
        assert reading["value"] == 9

    def test_a_skipped_week_still_gets_one_tare(self):
        h = _hist((1, 62, MON_4AM_ET), (2, 5, "2026-11-30T04:00:00-05:00"))
        tare, reading = cpu.beeminder_datapoints(h, reading_id=2)
        assert tare["requestid"] == "claude-tare-2026-11-23"
        assert reading["value"] == 5

    def test_old_reading_filed_after_a_newer_week_is_not_pushed(self):
        h = _hist((1, 62, MON_4AM_ET), (2, 3, NEXT_MON_4AM_ET), (3, 70, MON_4AM_ET))
        assert cpu.beeminder_datapoints(h, reading_id=3) == []

    def test_same_week_with_slightly_different_reset_time_is_one_week(self):
        h = _hist((1, 20, MON_4AM_ET), (2, 30, "2026-11-16T04:01:00-05:00"))
        assert [d["value"] for d in cpu.beeminder_datapoints(h, reading_id=2)] == [30]

    def test_order_of_history_does_not_matter(self):
        h = _hist((1, 62, MON_4AM_ET), (2, 3, NEXT_MON_4AM_ET))
        assert cpu.beeminder_datapoints(h, 2) == cpu.beeminder_datapoints(list(reversed(h)), 2)

    def test_reading_without_weekly_window_is_ignored(self):
        broken = {"id": 9, "windows": [{"kind": "session", "pct_used": 50, "resets_at": TONIGHT_8PM_ET}]}
        h = _hist((1, 10, MON_4AM_ET)) + [broken]
        assert cpu.beeminder_datapoints(h, reading_id=9) == []
        assert cpu.beeminder_datapoints(h, reading_id=1)[0]["value"] == 10

    def test_unknown_reading_id_is_not_pushed(self):
        assert cpu.beeminder_datapoints(_hist((1, 10, MON_4AM_ET)), reading_id=99) == []


class _FakeBeeminder:
    """Records calls. `errors` maps a request id to the exception that call raises."""

    def __init__(self, error=None, errors=None):
        self.calls, self.error, self.errors = [], error, errors or {}

    async def add_datapoint(self, goal_slug, value, comment="", requestid=None, daystamp=None, timestamp=None):
        self.calls.append((goal_slug, value, comment, requestid))
        self.timestamps = getattr(self, "timestamps", []) + [timestamp]
        error = self.errors.get(requestid, self.error)
        if error:
            raise error
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
    async def test_pushes_a_changed_reading(self):
        client = _FakeBeeminder()
        out = await cpu.sync_reading_to_beeminder(client, "claude-usage", _hist((1, 10, MON_4AM_ET)), 1)
        assert out == {"pushed": True, "goal": "claude-usage", "value": 10, "requestid": "claude-plan-1"}
        assert client.calls[0][:2] == ("claude-usage", 10) and client.calls[0][3] == "claude-plan-1"

    @pytest.mark.asyncio
    async def test_unchanged_reading_makes_no_call(self):
        client = _FakeBeeminder()
        h = _hist((1, 10, MON_4AM_ET), (2, 10, MON_4AM_ET))
        out = await cpu.sync_reading_to_beeminder(client, "claude-usage", h, 2)
        assert out["pushed"] is False and client.calls == []
        assert out["reason"] == "reading unchanged"

    @pytest.mark.asyncio
    async def test_new_week_sends_the_tare_before_the_reading(self):
        client = _FakeBeeminder()
        h = _hist((1, 62, MON_4AM_ET), (2, 3, NEXT_MON_4AM_ET))
        out = await cpu.sync_reading_to_beeminder(client, "claude-usage", h, 2)
        assert [(c[1], c[3]) for c in client.calls] == [(0, "claude-tare-2026-11-16"), (3, "claude-plan-2")]
        assert client.timestamps[0] is not None and client.timestamps[1] is None
        assert out == {"pushed": True, "goal": "claude-usage", "value": 3, "requestid": "claude-plan-2",
                       "tare": "claude-tare-2026-11-16"}

    @pytest.mark.asyncio
    async def test_tare_already_in_still_sends_the_reading(self):
        client = _FakeBeeminder(errors={"claude-tare-2026-11-16": _ApiError(422)})
        h = _hist((1, 62, MON_4AM_ET), (2, 3, NEXT_MON_4AM_ET))
        out = await cpu.sync_reading_to_beeminder(client, "claude-usage", h, 2)
        assert [c[3] for c in client.calls] == ["claude-tare-2026-11-16", "claude-plan-2"]
        assert out["pushed"] is True and out["value"] == 3

    @pytest.mark.asyncio
    async def test_failed_tare_holds_the_reading_back(self):
        """A raw 3 after last week's 62 with no tare would read as going backwards."""
        client = _FakeBeeminder(errors={"claude-tare-2026-11-16": _ApiError(500)})
        h = _hist((1, 62, MON_4AM_ET), (2, 3, NEXT_MON_4AM_ET))
        out = await cpu.sync_reading_to_beeminder(client, "claude-usage", h, 2)
        assert [c[3] for c in client.calls] == ["claude-tare-2026-11-16"]
        assert out["pushed"] is False and out["error"] == "_ApiError status=500"

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


# ---------------------------------------------------------------------------
# Status line readings (#383): source claude_code_cli, UTC offsets, fractional
# percentages, no weekly_fable, usually minutes old. The contract cases cover
# derive_state / summarize; these cover the store and the Beeminder graph.
# ---------------------------------------------------------------------------

MON_4AM_ET_IN_UTC = "2026-11-16T09:00:00+00:00"  # the same instant as MON_4AM_ET


def _status_line_row(weekly=26.0, session=30.0, observed=NOW - timedelta(minutes=7)):
    """A claude_plan_usage_readings row as the status line ingest stores it (live row #5's shape)."""
    windows = [{"kind": "weekly_all", "pct_used": weekly, "resets_at": MON_4AM_ET_IN_UTC}]
    if session is not None:
        windows.append({"kind": "session", "pct_used": session, "resets_at": "2026-11-13T21:50:00+00:00"})
    return {"plan": "ultra", "verified": False, "windows": windows, "source": "claude_code_cli",
            "observed_at": observed.isoformat(), "notes": "Claude Code status line"}


class TestStatusLineRows:
    def test_latest_reads_a_status_line_row(self):
        store = cpu.ClaudePlanUsageStore("postgres://fake")
        store._initialized = True
        row = _status_line_row()
        observed = datetime(2026, 11, 13, 19, 53, 41, 123456, tzinfo=timezone.utc)
        cur = MagicMock()
        # psycopg2 hands jsonb back already decoded, and timestamptz as a datetime.
        cur.fetchone.return_value = ("ultra", False, row["windows"], "claude_code_cli", observed, row["notes"])
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cur
        with patch("psycopg2.connect", return_value=conn):
            latest = store.latest("user-1")
        assert latest["source"] == "claude_code_cli"
        assert latest["observed_at"] == "2026-11-13T19:53:41.123456+00:00"
        status = cpu.summarize(latest, NOW)
        assert status["state"] == "available" and status["stale"] is False
        assert status["reason"] == "session at 30%"
        assert status["summary_line"] == "Claude: available (26% weekly, resets Mon 4:00 AM)"
        assert status["source"] == "claude_code_cli"

    def test_minutes_old_reading_is_fresh(self):
        assert cpu.derive_state(_status_line_row(observed=NOW - timedelta(minutes=3)), NOW)["stale"] is False

    def test_no_weekly_fable_and_no_session_is_still_judged(self):
        status = cpu.summarize(_status_line_row(weekly=81.5, session=None), NOW)
        assert status["state"] == "constrained"
        assert status["reason"] == "weekly_all at 82%"

    def test_manual_and_status_line_readings_of_one_week_are_one_week(self):
        """A manual 23 at -05:00, then a status line 26.0 at +00:00 for the same reset: one week, no tare."""
        history = _hist((4, 23, MON_4AM_ET)) + [{**_status_line_row(26.0), "id": 5}]
        (dp,) = cpu.beeminder_datapoints(history, reading_id=5)
        assert dp["value"] == 26
        assert "26% of this week" in dp["comment"] and "resets Mon 4:00 AM" in dp["comment"]
        assert dp["requestid"] == "claude-plan-5"

    def test_fractional_status_line_pct_reaches_the_graph_unrounded(self):
        history = _hist((4, 23, MON_4AM_ET)) + [{**_status_line_row(23.5), "id": 5}]
        (dp,) = cpu.beeminder_datapoints(history, reading_id=5)
        assert dp["value"] == 23.5
        assert "23.5% of this week" in dp["comment"]

    def test_status_line_reading_below_the_manual_peak_is_not_pushed(self):
        history = _hist((4, 23, MON_4AM_ET)) + [{**_status_line_row(22.5), "id": 5}]
        assert cpu.beeminder_datapoints(history, reading_id=5) == []
