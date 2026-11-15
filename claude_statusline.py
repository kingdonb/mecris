#!/usr/bin/env python3
"""
Claude plan usage from the Claude Code status line (kingdonb/mecris#344).

Claude Code runs a configured status line command and hands it a JSON document
on stdin. For subscribers that document carries the plan's rate limits:

    "rate_limits": {
      "five_hour": {"used_percentage": 23.5, "resets_at": 1738425600},
      "seven_day": {"used_percentage": 41.2, "resets_at": 1738857600}
    }

This is a documented interface (https://code.claude.com/docs/en/statusline), so
nothing is scraped and no credential is read. `scripts/claude_statusline.py` is
the command; it writes the windows to a snapshot file (~/.claude/usage.json)
that any local dashboard can read, and prints a short line for the status bar.
The MCP server reads the same file and records it as a `claude_code_cli` reading.

Limits of the source:
- It only speaks while a Claude Code session is making requests. Usage from
  claude.ai or the desktop app shows up at the next Claude Code response.
- There is no per-model weekly window (`weekly_fable`); that one stays manual.
- `rate_limits` is absent before a session's first response, and a window is
  dropped once its reset time passes. Every field is optional here.

Standard library only, and Python 3.9 compatible: the command may be run by the
system interpreter, several times a minute.
"""

import json
import math
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import claude_plan_usage as cpu

SCHEMA = 1
SOURCE = "claude_code_cli"
SNAPSHOT_ENV = "CLAUDE_USAGE_SNAPSHOT"
# Status line field -> the window kind used by claude_plan_usage readings.
RATE_LIMIT_KINDS = (("seven_day", "weekly_all"), ("five_hour", "session"))
LABELS = (("session", "5h"), ("weekly_all", "wk"))
WAITING_TEXT = "plan usage: waiting"
# How many sessions' progress markers to remember in the snapshot.
MAX_SESSIONS = 20
# A changed reading is stored at most this often, unless the state changes.
MIN_RECORD_INTERVAL = timedelta(minutes=15)
# Smaller moves than this are not a change worth a database row.
MIN_PCT_CHANGE = 1.0


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def windows_from_payload(payload: Any) -> List[Dict[str, Any]]:
    """The plan windows in a status line payload. Anything malformed is skipped."""
    limits = payload.get("rate_limits") if isinstance(payload, dict) else None
    if not isinstance(limits, dict):
        return []
    windows = []
    for field, kind in RATE_LIMIT_KINDS:
        window = limits.get(field)
        if not isinstance(window, dict):
            continue
        pct = _number(window.get("used_percentage"))
        resets = _number(window.get("resets_at"))
        if pct is None or resets is None:
            continue
        try:
            resets_at = datetime.fromtimestamp(resets, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            continue
        windows.append({"kind": kind, "pct_used": min(100.0, max(0.0, pct)), "resets_at": resets_at})
    return windows


def _valid_snapshot(snapshot: Any) -> Optional[Dict[str, Any]]:
    """`snapshot` if it is one this version wrote and can trust, else None."""
    if not isinstance(snapshot, dict) or snapshot.get("schema") != SCHEMA:
        return None
    windows = snapshot.get("windows")
    if not isinstance(windows, list) or not windows:
        return None
    try:
        for w in windows:
            if w["kind"] not in cpu.WINDOW_KINDS or _number(w["pct_used"]) is None:
                return None
            if not 0 <= w["pct_used"] <= 100 or cpu._parse_dt(w["resets_at"]) is None:
                return None
        if cpu._parse_dt(snapshot.get("observed_at")) is None:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return snapshot


def _is_older(windows: List[Dict[str, Any]], previous: List[Dict[str, Any]]) -> bool:
    """True when `windows` is an earlier look at the same windows as `previous`.

    Usage only rises within a window, so the same reset times with nothing
    higher and something lower means these numbers were read earlier.
    """
    before = {w["kind"]: w for w in previous}
    lower = False
    for w in windows:
        prior = before.get(w["kind"])
        if prior is None or prior["resets_at"] != w["resets_at"]:
            return False
        if w["pct_used"] > prior["pct_used"]:
            return False
        lower = lower or w["pct_used"] < prior["pct_used"]
    return lower


def build_snapshot(payload: Any, previous: Any, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """The snapshot to write for this status line run, or None to leave the file alone.

    `observed_at` is when these numbers last arrived with an API response. The
    status line also re-runs on timers and mode changes with the same payload,
    and several sessions share one file, so a run only counts as a fresh
    observation when its session has made a request since it last wrote
    (`cost.total_api_duration_ms` moved), or the numbers themselves are new.
    """
    now = now or datetime.now(timezone.utc)
    windows = windows_from_payload(payload)
    if not windows:
        return None
    previous = _valid_snapshot(previous)
    sessions = dict(previous.get("sessions") or {}) if previous else {}

    session_id = payload.get("session_id")
    session_id = session_id if isinstance(session_id, str) and session_id else None
    cost = payload.get("cost")
    api_ms = _number(cost.get("total_api_duration_ms")) if isinstance(cost, dict) else None

    seen = session_id is not None and session_id in sessions
    new_response = seen and api_ms is not None and sessions[session_id] != api_ms
    if previous and not new_response and _is_older(windows, previous["windows"]):
        return None  # an idle session re-rendering numbers another one has passed

    fresh = previous is None or new_response or not seen or windows != previous["windows"]
    if session_id is not None:
        sessions.pop(session_id, None)
        sessions[session_id] = api_ms
        for stale in list(sessions)[:-MAX_SESSIONS]:
            del sessions[stale]

    snapshot = {
        "schema": SCHEMA,
        "source": SOURCE,
        "observed_at": now.isoformat() if fresh else previous["observed_at"],
        "checked_at": now.isoformat(),
        "windows": windows,
        "sessions": sessions,
    }
    version = payload.get("version")
    if isinstance(version, str):
        snapshot["claude_code_version"] = version
    return snapshot


def status_text(windows: List[Dict[str, Any]], now: Optional[datetime] = None) -> str:
    """'5h 16% · wk 24%'. With `now`, windows that have already reset are left out.

    Halves round to even (22.5 -> 22, 23.5 -> 24), as claude_plan_usage.summarize,
    Spin and Android do, so every arm shows the same number.
    """
    by_kind = {}
    for w in windows:
        if now is not None and cpu._parse_dt(w["resets_at"]) <= now:
            continue
        by_kind[w["kind"]] = w
    parts = [f"{label} {by_kind[kind]['pct_used']:.0f}%"
             for kind, label in LABELS if kind in by_kind]
    return " · ".join(parts) if parts else WAITING_TEXT


def snapshot_path() -> Path:
    override = os.environ.get(SNAPSHOT_ENV, "").strip()
    return Path(override).expanduser() if override else Path.home() / ".claude" / "usage.json"


def write_snapshot(path: Any, snapshot: Dict[str, Any]) -> None:
    """Write atomically: Claude Code cancels a status line run that is overtaken
    by the next one, and a reader must never see half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")  # mode 0600
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(snapshot, f, indent=2)
            f.write("\n")
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_snapshot(path: Any) -> Optional[Dict[str, Any]]:
    """The snapshot file's content, or None if it is missing or not usable."""
    try:
        with open(str(path)) as f:
            return _valid_snapshot(json.load(f))
    except (OSError, ValueError):
        return None


def load_reading(path: Any) -> Optional[Dict[str, Any]]:
    """The snapshot file as a claude_plan_usage reading, or None."""
    snapshot = read_snapshot(path)
    if snapshot is None:
        return None
    windows = [{"kind": w["kind"], "pct_used": float(w["pct_used"]),
                "resets_at": cpu._parse_dt(w["resets_at"]).isoformat()} for w in snapshot["windows"]]
    return cpu.make_reading(windows, source=SOURCE, observed_at=snapshot["observed_at"],
                            notes="Claude Code status line")


def freshest(local: Optional[Dict[str, Any]], stored: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The later observation of the two; the stored one on a tie."""
    if local is None or stored is None:
        return stored if local is None else local
    return local if cpu._parse_dt(local["observed_at"]) > cpu._parse_dt(stored["observed_at"]) else stored


def _changed(local: Dict[str, Any], stored: Dict[str, Any]) -> bool:
    """Do the windows the status line reports differ from the stored reading's?"""
    kinds = [kind for _, kind in RATE_LIMIT_KINDS]
    ours = {w["kind"]: w for w in local["windows"] if w["kind"] in kinds}
    theirs = {w["kind"]: w for w in stored.get("windows") or [] if w["kind"] in kinds}
    if set(ours) != set(theirs):
        return True
    return any(abs(ours[k]["pct_used"] - theirs[k]["pct_used"]) >= MIN_PCT_CHANGE for k in ours)


def should_record(local: Optional[Dict[str, Any]], stored: Optional[Dict[str, Any]],
                  now: Optional[datetime] = None,
                  min_interval: timedelta = MIN_RECORD_INTERVAL) -> bool:
    """Is the local reading worth storing, given the latest stored one?

    The status line runs on every response, so storing each run would flood the
    table. A reading is stored when it is newer and its numbers have moved, and
    then at most once per `min_interval`. A change of state (say available to
    constrained) or a new week is stored at once.
    """
    now = now or datetime.now(timezone.utc)
    if local is None:
        return False
    local_state = cpu.derive_state(local, now)
    if local_state["stale"]:
        return False
    if stored is None:
        return True
    age = cpu._parse_dt(local["observed_at"]) - cpu._parse_dt(stored["observed_at"])
    if age <= timedelta(0):
        return False
    if cpu.derive_state(stored, now)["state"] != local_state["state"]:
        return True
    local_week, stored_week = cpu._weekly_point(local), cpu._weekly_point(stored)
    if local_week and stored_week and local_week[0] != stored_week[0]:
        return True
    return _changed(local, stored) and age >= min_interval


def pending_reading(path: Any, stored: Optional[Dict[str, Any]],
                    now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """The reading in the snapshot file if it should be stored now, else None."""
    reading = load_reading(path)
    return reading if should_record(reading, stored, now) else None


def main(stdin: Any = None, stdout: Any = None) -> int:
    """The status line command. It always prints one line and returns 0: a
    status bar must not break a session, whatever it was fed."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    text = WAITING_TEXT
    try:
        now = datetime.now(timezone.utc)
        path = snapshot_path()
        try:
            payload = json.loads(stdin.read())
        except ValueError:
            payload = None
        previous = read_snapshot(path)
        snapshot = build_snapshot(payload, previous, now)
        if snapshot is not None:
            try:
                write_snapshot(path, snapshot)
            except OSError:
                pass  # still show the numbers we were given
        shown = snapshot or previous
        if shown is not None:
            text = status_text(shown["windows"], now)
    except Exception:
        text = WAITING_TEXT
    stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
