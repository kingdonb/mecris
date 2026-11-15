"""Tests for reading Claude plan usage from the Claude Code status line (kingdonb/mecris#344).

Claude Code hands its status line command a JSON document on stdin. For
subscribers it carries `rate_limits.five_hour` and `rate_limits.seven_day`,
each with `used_percentage` (0-100) and `resets_at` (Unix epoch seconds).
"""

import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import claude_plan_usage as cpu
import claude_statusline as cs

NOW = datetime(2026, 11, 14, 23, 50, tzinfo=timezone.utc)  # Sat 6:50 PM ET
SESSION_RESET = datetime(2026, 11, 15, 0, 50, tzinfo=timezone.utc)
WEEK_RESET = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)  # Mon 4 AM ET
SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "claude_statusline.py"


def _payload(five=16.4, seven=23.5, session_id="s1", api_ms=2300,
             five_reset=SESSION_RESET, seven_reset=WEEK_RESET):
    limits = {}
    if five is not None:
        limits["five_hour"] = {"used_percentage": five, "resets_at": int(five_reset.timestamp())}
    if seven is not None:
        limits["seven_day"] = {"used_percentage": seven, "resets_at": int(seven_reset.timestamp())}
    payload = {"session_id": session_id, "version": "2.1.325",
               "cost": {"total_api_duration_ms": api_ms}}
    if limits:
        payload["rate_limits"] = limits
    return payload


def _stored(weekly=23.5, session=16.4, observed=NOW, week_reset=WEEK_RESET, source="manual"):
    windows = cpu.build_windows(
        weekly, week_reset.isoformat(),
        session_pct=session,
        session_resets_at=SESSION_RESET.isoformat() if session is not None else None,
    )
    return cpu.make_reading(windows, source=source, observed_at=observed.isoformat())


class TestWindowsFromPayload:
    def test_maps_five_hour_to_session_and_seven_day_to_weekly_all(self):
        windows = cs.windows_from_payload(_payload())
        assert windows == [
            {"kind": "weekly_all", "pct_used": 23.5, "resets_at": WEEK_RESET.isoformat()},
            {"kind": "session", "pct_used": 16.4, "resets_at": SESSION_RESET.isoformat()},
        ]

    def test_no_rate_limits_is_no_windows(self):
        # Before the session's first API response, and for non-subscribers.
        assert cs.windows_from_payload({"session_id": "s1"}) == []

    def test_each_window_may_be_absent(self):
        # A verified Ultra account has no five-hour window.
        windows = cs.windows_from_payload(_payload(five=None))
        assert [w["kind"] for w in windows] == ["weekly_all"]

    def test_spend_limit_is_ignored(self):
        # Gateway spend limits are dollars, not the subscription pool.
        payload = _payload()
        payload["rate_limits"]["spend_limit"] = {"used_percentage": 62.8, "resets_at": 1740787200}
        assert [w["kind"] for w in cs.windows_from_payload(payload)] == ["weekly_all", "session"]

    def test_over_100_is_clamped(self):
        windows = cs.windows_from_payload(_payload(seven=104.2))
        assert windows[0]["pct_used"] == 100.0

    @pytest.mark.parametrize("bad", [
        {"used_percentage": "lots", "resets_at": 1738425600},
        {"used_percentage": 20},
        {"used_percentage": None, "resets_at": 1738425600},
        {"used_percentage": 20, "resets_at": "soon"},
        "23%",
        None,
    ])
    def test_malformed_window_is_skipped_not_raised(self, bad):
        payload = _payload()
        payload["rate_limits"]["five_hour"] = bad
        assert [w["kind"] for w in cs.windows_from_payload(payload)] == ["weekly_all"]

    @pytest.mark.parametrize("payload", [None, [], "x", {"rate_limits": []}, {"rate_limits": None}])
    def test_malformed_payload_is_no_windows(self, payload):
        assert cs.windows_from_payload(payload) == []


class TestBuildSnapshot:
    def test_first_snapshot(self):
        snap = cs.build_snapshot(_payload(), None, NOW)
        assert snap["schema"] == 1
        assert snap["source"] == "claude_code_cli"
        assert snap["observed_at"] == NOW.isoformat()
        assert snap["checked_at"] == NOW.isoformat()
        assert [w["kind"] for w in snap["windows"]] == ["weekly_all", "session"]
        assert snap["claude_code_version"] == "2.1.325"

    def test_no_windows_is_no_snapshot(self):
        # Never overwrite a good snapshot with an empty one.
        assert cs.build_snapshot({"session_id": "s1"}, None, NOW) is None

    def test_rerun_without_a_new_api_response_keeps_observed_at(self):
        # The status line also re-runs on mode changes and timers. That is the
        # same data as before, so it must not be re-stamped as fresh.
        first = cs.build_snapshot(_payload(), None, NOW)
        later = NOW + timedelta(hours=3)
        again = cs.build_snapshot(_payload(), first, later)
        assert again["observed_at"] == NOW.isoformat()
        assert again["checked_at"] == later.isoformat()

    def test_new_api_response_refreshes_observed_at_even_if_unchanged(self):
        first = cs.build_snapshot(_payload(api_ms=2300), None, NOW)
        later = NOW + timedelta(minutes=5)
        again = cs.build_snapshot(_payload(api_ms=9900), first, later)
        assert again["observed_at"] == later.isoformat()

    def test_another_session_refreshes_observed_at(self):
        first = cs.build_snapshot(_payload(session_id="s1"), None, NOW)
        later = NOW + timedelta(minutes=5)
        again = cs.build_snapshot(_payload(session_id="s2"), first, later)
        assert again["observed_at"] == later.isoformat()

    def test_changed_windows_refresh_observed_at(self):
        first = cs.build_snapshot(_payload(seven=23.5), None, NOW)
        later = NOW + timedelta(minutes=5)
        again = cs.build_snapshot(_payload(seven=24.1), first, later)
        assert again["observed_at"] == later.isoformat()

    def test_idle_session_rerun_does_not_restamp_another_sessions_reading(self):
        # Sessions a and b both wrote; a then idles and re-renders the same numbers.
        first = cs.build_snapshot(_payload(session_id="a", api_ms=100), None, NOW)
        second = cs.build_snapshot(_payload(session_id="b", api_ms=50), first, NOW + timedelta(minutes=1))
        later = NOW + timedelta(hours=2)
        again = cs.build_snapshot(_payload(session_id="a", api_ms=100), second, later)
        assert again["observed_at"] == second["observed_at"]

    def test_new_response_with_lower_numbers_is_believed(self):
        # If Anthropic lowers a figure mid-window, a real response wins.
        first = cs.build_snapshot(_payload(seven=40.0, api_ms=100), None, NOW)
        later = NOW + timedelta(minutes=5)
        again = cs.build_snapshot(_payload(seven=10.0, api_ms=200), first, later)
        assert again["windows"][0]["pct_used"] == 10.0
        assert again["observed_at"] == later.isoformat()

    def test_remembers_a_bounded_number_of_sessions(self):
        snap = None
        for i in range(cs.MAX_SESSIONS + 5):
            snap = cs.build_snapshot(_payload(session_id=f"s{i}"), snap, NOW)
        assert len(snap["sessions"]) == cs.MAX_SESSIONS
        assert f"s{cs.MAX_SESSIONS + 4}" in snap["sessions"]

    def test_stale_tab_does_not_overwrite_a_newer_reading(self):
        # Two sessions share one file. An idle one re-rendering old numbers
        # must not replace what the active one wrote. Usage only goes up
        # within a window, so lower numbers for the same window are older.
        active = cs.build_snapshot(_payload(session_id="active", five=40.0, seven=30.0), None, NOW)
        later = NOW + timedelta(minutes=5)
        idle = cs.build_snapshot(_payload(session_id="idle", five=16.4, seven=23.5), active, later)
        assert idle is None

    def test_lower_numbers_after_a_reset_are_accepted(self):
        before = cs.build_snapshot(_payload(seven=97.0, five=None), None, NOW)
        next_week = WEEK_RESET + timedelta(days=7)
        later = WEEK_RESET + timedelta(hours=1)
        after = cs.build_snapshot(_payload(seven=1.0, five=None, seven_reset=next_week), before, later)
        assert after["windows"][0]["pct_used"] == 1.0
        assert after["observed_at"] == later.isoformat()

    @pytest.mark.parametrize("previous", ["junk", [], {"windows": "x"}, {"schema": 99}])
    def test_unreadable_previous_snapshot_is_ignored(self, previous):
        snap = cs.build_snapshot(_payload(), previous, NOW)
        assert snap["observed_at"] == NOW.isoformat()


class TestStatusText:
    def test_both_windows(self):
        assert cs.status_text(cs.windows_from_payload(_payload())) == "5h 16% · wk 24%"

    def test_weekly_only(self):
        assert cs.status_text(cs.windows_from_payload(_payload(five=None))) == "wk 24%"

    def test_nothing_known(self):
        assert cs.status_text([]) == "plan usage: waiting"

    @pytest.mark.parametrize("pct, shown", [(22.5, "22"), (23.5, "24"), (80.5, "80")])
    def test_halves_round_to_even_like_every_other_arm(self, pct, shown):
        # summarize ('{:.0f}'), Spin ('{:.0}') and Android (HALF_EVEN) all round a
        # half to the even neighbour; the status bar must show the same number.
        window = {"kind": "weekly_all", "pct_used": pct, "resets_at": WEEK_RESET.isoformat()}
        assert cs.status_text([window]) == f"wk {shown}%"
        assert f"{shown}% weekly" in cpu.summarize(cpu.make_reading([window], observed_at=NOW.isoformat()), NOW)["summary_line"]


class TestSnapshotFile:
    def test_roundtrip_gives_a_recordable_reading(self, tmp_path):
        path = tmp_path / "usage.json"
        cs.write_snapshot(path, cs.build_snapshot(_payload(), None, NOW))
        reading = cs.load_reading(path)
        assert reading["source"] == "claude_code_cli"
        assert reading["plan"] == "ultra"
        assert reading["observed_at"] == NOW.isoformat()
        assert reading["verified"] is False  # a session window is still shown
        assert cpu.summarize(reading, NOW)["state"] == "available"

    def test_file_is_private_and_leaves_no_temp_file(self, tmp_path):
        path = tmp_path / "usage.json"
        cs.write_snapshot(path, cs.build_snapshot(_payload(), None, NOW))
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert [p.name for p in tmp_path.iterdir()] == ["usage.json"]

    def test_creates_missing_directory(self, tmp_path):
        path = tmp_path / "nested" / "usage.json"
        cs.write_snapshot(path, cs.build_snapshot(_payload(), None, NOW))
        assert path.exists()

    def test_missing_file_is_no_reading(self, tmp_path):
        assert cs.load_reading(tmp_path / "nope.json") is None

    @pytest.mark.parametrize("content", [
        "", "not json", "[]", '{"windows": []}', '{"windows": [{"kind": "session"}]}',
        '{"observed_at": "yesterday-ish", "windows": [{"kind": "weekly_all", "pct_used": 5, '
        '"resets_at": "2026-11-16T09:00:00+00:00"}]}',
        '{"observed_at": "2026-11-14T23:50:00+00:00", "windows": [{"kind": "weekly_all", '
        '"pct_used": 500, "resets_at": "2026-11-16T09:00:00+00:00"}]}',
        '{"observed_at": "2026-11-14T23:50:00+00:00", "windows": [{"kind": "weekly_opus", '
        '"pct_used": 5, "resets_at": "2026-11-16T09:00:00+00:00"}]}',
    ])
    def test_malformed_file_is_no_reading(self, tmp_path, content):
        path = tmp_path / "usage.json"
        path.write_text(content)
        assert cs.load_reading(path) is None

    def test_default_path_and_override(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_USAGE_SNAPSHOT", raising=False)
        assert cs.snapshot_path() == Path.home() / ".claude" / "usage.json"
        monkeypatch.setenv("CLAUDE_USAGE_SNAPSHOT", str(tmp_path / "u.json"))
        assert cs.snapshot_path() == tmp_path / "u.json"


class TestFreshest:
    def test_picks_the_later_observation(self):
        local = _stored(weekly=30, observed=NOW, source="claude_code_cli")
        stored = _stored(weekly=23, observed=NOW - timedelta(hours=2))
        assert cs.freshest(local, stored) is local
        assert cs.freshest(stored, local) is local

    def test_one_side_missing(self):
        reading = _stored()
        assert cs.freshest(None, reading) is reading
        assert cs.freshest(reading, None) is reading
        assert cs.freshest(None, None) is None

    def test_tie_prefers_the_stored_reading(self):
        local = _stored(source="claude_code_cli")
        stored = _stored()
        assert cs.freshest(local, stored) is stored


class TestShouldRecord:
    """Which local readings are worth a database row (and a Beeminder look)."""

    def _local(self, **kw):
        kw.setdefault("source", "claude_code_cli")
        return _stored(**kw)

    def test_nothing_local(self):
        assert cs.should_record(None, _stored(), now=NOW) is False

    def test_first_reading_ever(self):
        assert cs.should_record(self._local(), None, now=NOW) is True

    def test_local_not_newer_than_stored(self):
        stored = _stored(observed=NOW)
        assert cs.should_record(self._local(observed=NOW - timedelta(minutes=1)), stored, now=NOW) is False
        assert cs.should_record(self._local(observed=NOW), stored, now=NOW) is False

    def test_same_numbers_are_not_recorded_again(self):
        stored = _stored(weekly=23.5, session=16.4, observed=NOW - timedelta(hours=5))
        assert cs.should_record(self._local(weekly=23.5, session=16.4), stored, now=NOW) is False

    def test_sub_point_wobble_is_not_a_change(self):
        stored = _stored(weekly=23.4, session=16.0, observed=NOW - timedelta(hours=5))
        assert cs.should_record(self._local(weekly=23.6, session=16.3), stored, now=NOW) is False

    def test_changed_numbers_wait_out_the_throttle(self):
        stored = _stored(weekly=23, observed=NOW - timedelta(minutes=5))
        assert cs.should_record(self._local(weekly=26), stored, now=NOW) is False

    def test_changed_numbers_after_the_throttle(self):
        stored = _stored(weekly=23, observed=NOW - timedelta(minutes=16))
        assert cs.should_record(self._local(weekly=26), stored, now=NOW) is True

    def test_state_change_skips_the_throttle(self):
        stored = _stored(weekly=79, observed=NOW - timedelta(minutes=1))
        assert cs.should_record(self._local(weekly=85), stored, now=NOW) is True

    def test_new_week_skips_the_throttle(self):
        stored = _stored(weekly=97, session=None, observed=NOW - timedelta(minutes=1))
        local = self._local(weekly=1, session=None, week_reset=WEEK_RESET + timedelta(days=7))
        assert cs.should_record(local, stored, now=NOW) is True

    def test_already_expired_local_reading_is_not_recorded(self):
        # The laptop was closed all week: the file is from before the reset.
        local = self._local(weekly=50, session=None, observed=NOW - timedelta(days=3),
                            week_reset=NOW - timedelta(days=1))
        assert cs.should_record(local, None, now=NOW) is False

    def test_pending_reading_reads_the_file(self, tmp_path):
        path = tmp_path / "usage.json"
        cs.write_snapshot(path, cs.build_snapshot(_payload(), None, NOW))
        assert cs.pending_reading(path, None, now=NOW)["source"] == "claude_code_cli"
        assert cs.pending_reading(path, cs.load_reading(path), now=NOW) is None
        assert cs.pending_reading(tmp_path / "nope.json", None, now=NOW) is None


class TestScript:
    """The command Claude Code runs. It must always print a line and exit 0."""

    def _run(self, stdin, tmp_path):
        env = {**os.environ, "CLAUDE_USAGE_SNAPSHOT": str(tmp_path / "usage.json")}
        return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, env=env,
                              capture_output=True, text=True, timeout=20)

    def _live_payload(self):
        # The script uses the real clock, so these windows must not have reset.
        return _payload(five_reset=datetime.now(timezone.utc) + timedelta(hours=1),
                        seven_reset=datetime.now(timezone.utc) + timedelta(days=2))

    def test_writes_snapshot_and_prints_line(self, tmp_path):
        result = self._run(json.dumps(self._live_payload()), tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == "5h 16% · wk 24%"
        snap = json.loads((tmp_path / "usage.json").read_text())
        assert [w["pct_used"] for w in snap["windows"]] == [23.5, 16.4]

    def test_no_rate_limits_keeps_the_existing_snapshot(self, tmp_path):
        self._run(json.dumps(self._live_payload()), tmp_path)
        before = (tmp_path / "usage.json").read_text()
        result = self._run(json.dumps({"session_id": "s2"}), tmp_path)
        assert result.returncode == 0
        assert (tmp_path / "usage.json").read_text() == before
        # The line shows what is on file rather than going blank.
        assert result.stdout.strip() == "5h 16% · wk 24%"

    def test_windows_on_file_that_have_reset_are_not_shown(self, tmp_path):
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        cs.write_snapshot(tmp_path / "usage.json", cs.build_snapshot(
            _payload(five_reset=past, seven_reset=past + timedelta(days=2)), None, past - timedelta(hours=1)))
        result = self._run(json.dumps({"session_id": "s2"}), tmp_path)
        assert result.stdout.strip() == "wk 24%"

    @pytest.mark.parametrize("stdin", ["", "not json", "[1, 2]"])
    def test_garbage_in_still_exits_zero(self, tmp_path, stdin):
        result = self._run(stdin, tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == "plan usage: waiting"
        assert not (tmp_path / "usage.json").exists()

    def test_unwritable_snapshot_still_prints(self, tmp_path):
        blocker = tmp_path / "blocker"
        blocker.write_text("a file where a directory is needed")
        env = {**os.environ, "CLAUDE_USAGE_SNAPSHOT": str(blocker / "usage.json")}
        result = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(self._live_payload()), env=env,
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == 0
        assert result.stdout.strip() == "5h 16% · wk 24%"
