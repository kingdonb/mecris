#!/usr/bin/env python3
"""
Claude plan usage telemetry (kingdonb/mecris#344).

Tracks *subscription plan limit usage* (e.g. the Ultra plan's weekly windows),
not dollars and not usage credits. There is no official API for consumer plan
usage, so readings are recorded (manually, or by a local `/usage` parser) and
judged for staleness: a reading is never assumed fresh.

Pure logic (parsing, derived state, summary text) lives in module-level
functions so it can be tested without a database.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("claude_plan_usage")

WINDOW_KINDS = ("session", "weekly_all", "weekly_fable")
SOURCES = ("manual", "claude_code_cli", "web_endpoint")
CONSTRAINED_PCT = 80.0
EXHAUSTED_PCT = 100.0
# Even if no window has reset yet, a reading this old is not trusted.
MAX_READING_AGE = timedelta(hours=24)

STATE_AVAILABLE = "available"
STATE_CONSTRAINED = "constrained"
STATE_EXHAUSTED = "exhausted"
STATE_UNKNOWN = "unknown"


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp. Naive values are treated as UTC."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def build_windows(
    weekly_all_pct: Optional[float] = None,
    weekly_all_resets_at: Optional[str] = None,
    weekly_fable_pct: Optional[float] = None,
    weekly_fable_resets_at: Optional[str] = None,
    session_pct: Optional[float] = None,
    session_resets_at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Build the windows[] list from flat tool arguments, validating each."""
    raw = [
        ("weekly_all", weekly_all_pct, weekly_all_resets_at),
        ("weekly_fable", weekly_fable_pct, weekly_fable_resets_at),
        ("session", session_pct, session_resets_at),
    ]
    windows = []
    for kind, pct, resets_at in raw:
        if pct is None:
            continue
        pct = float(pct)
        if pct < 0 or pct > 100:
            raise ValueError(f"{kind}: pct_used must be between 0 and 100, got {pct}")
        reset_dt = _parse_dt(resets_at)
        if reset_dt is None:
            raise ValueError(f"{kind}: resets_at is required when pct_used is given")
        windows.append({"kind": kind, "pct_used": pct, "resets_at": reset_dt.isoformat()})
    if not windows:
        raise ValueError("At least one window (e.g. weekly_all_pct + weekly_all_resets_at) is required")
    return windows


def infer_verified(windows: List[Dict[str, Any]], verified: Optional[bool]) -> Optional[bool]:
    """An explicit flag wins; otherwise a missing session window implies verified."""
    if verified is not None:
        return verified
    if any(w["kind"] == "session" for w in windows):
        return False
    return None


def derive_state(reading: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Derive availability from a reading.

    - A window whose reset time has passed is stale (its usage has reset since
      we looked), so it is excluded rather than assumed fresh.
    - A reading older than MAX_READING_AGE is stale as a whole.
    - With no fresh weekly_all window, the state is unknown.
    """
    now = now or datetime.now(timezone.utc)
    if not reading:
        return {"state": STATE_UNKNOWN, "reason": "no reading recorded", "fresh_windows": [], "stale": True}

    observed = _parse_dt(reading.get("observed_at"))
    if observed is None or now - observed > MAX_READING_AGE:
        return {"state": STATE_UNKNOWN, "reason": "reading is stale", "fresh_windows": [], "stale": True}

    fresh = []
    for w in reading.get("windows") or []:
        reset = _parse_dt(w.get("resets_at"))
        if reset is not None and reset > now:
            fresh.append(w)

    if not any(w["kind"] == "weekly_all" for w in fresh):
        return {"state": STATE_UNKNOWN, "reason": "weekly window has reset since the last reading",
                "fresh_windows": fresh, "stale": True}

    worst = max(fresh, key=lambda w: w["pct_used"])
    if worst["pct_used"] >= EXHAUSTED_PCT:
        state = STATE_EXHAUSTED
    elif worst["pct_used"] > CONSTRAINED_PCT:
        state = STATE_CONSTRAINED
    else:
        state = STATE_AVAILABLE
    return {"state": state, "reason": f"{worst['kind']} at {worst['pct_used']:.0f}%",
            "binding_window": worst, "fresh_windows": fresh, "stale": False}


def _fmt_reset(resets_at: str, tz_name: str = "America/New_York") -> str:
    from zoneinfo import ZoneInfo
    dt = _parse_dt(resets_at).astimezone(ZoneInfo(tz_name))
    return dt.strftime("%a %-I:%M %p")


def summarize(reading: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Full status payload, including a one-line human summary."""
    derived = derive_state(reading, now)
    state = derived["state"]
    if state == STATE_UNKNOWN:
        line = f"Claude: unknown ({derived['reason']})"
    else:
        weekly = next(w for w in derived["fresh_windows"] if w["kind"] == "weekly_all")
        line = f"Claude: {state} ({weekly['pct_used']:.0f}% weekly, resets {_fmt_reset(weekly['resets_at'])})"
        binding = derived["binding_window"]
        if binding["kind"] != "weekly_all" and state != STATE_AVAILABLE:
            line += f"; {binding['kind']} {binding['pct_used']:.0f}%"
    return {
        "state": state,
        "reason": derived["reason"],
        "stale": derived["stale"],
        "summary_line": line,
        "plan": reading.get("plan") if reading else None,
        "verified": reading.get("verified") if reading else None,
        "source": reading.get("source") if reading else None,
        "observed_at": reading.get("observed_at") if reading else None,
        "windows": reading.get("windows", []) if reading else [],
    }


# --- Beeminder graph (kingdonb/mecris#371) -----------------------------------
#
# The goal is a do-more odometer of plan usage. Weekly usage resets to 0 every
# week, so the datapoint is a running total instead: each week's highest
# reading, added up. 100 means one full week's allowance. The total never
# drops, whatever Beeminder does with resets.

def _weekly_point(reading: Dict[str, Any]) -> Optional[tuple]:
    """(week key, percent used) for a reading's weekly_all window, if it has one."""
    for w in reading.get("windows") or []:
        if w.get("kind") == "weekly_all":
            resets = _parse_dt(w.get("resets_at"))
            if resets is None or w.get("pct_used") is None:
                return None
            # Weekly resets are 7 days apart, so the UTC date identifies the week
            # even when the same reset time is typed in slightly differently.
            return resets.astimezone(timezone.utc).date().isoformat(), float(w["pct_used"])
    return None


def _tidy(value: float) -> float:
    rounded = round(value, 2)
    return int(rounded) if rounded == int(rounded) else rounded


def cumulative_weekly_pct(readings: List[Dict[str, Any]]) -> float:
    """Running total of plan usage: the highest weekly_all reading of each week, summed."""
    peak_by_week: Dict[str, float] = {}
    for reading in readings:
        point = _weekly_point(reading)
        if point:
            week, pct = point
            peak_by_week[week] = max(peak_by_week.get(week, 0.0), pct)
    return _tidy(sum(peak_by_week.values()))


def beeminder_datapoint(history: List[Dict[str, Any]], reading_id: Any) -> Optional[Dict[str, Any]]:
    """Datapoint to push for the reading `reading_id`, or None if it changes nothing.

    `history` is every stored reading for the user, each with an "id". The request
    id comes from the reading id, so retrying the same reading cannot duplicate it.
    """
    current = next((r for r in history if r.get("id") == reading_id), None)
    if current is None:
        return None
    point = _weekly_point(current)
    if point is None:
        return None
    total = cumulative_weekly_pct(history)
    before = cumulative_weekly_pct([r for r in history if r.get("id") != reading_id])
    if total == before:
        return None
    weekly = next(w for w in current["windows"] if w.get("kind") == "weekly_all")
    comment = (f"Claude {current.get('plan', 'plan')}: {_tidy(point[1])}% of this week used, "
               f"resets {_fmt_reset(weekly['resets_at'])} (running total {total})")
    return {"value": total, "comment": comment, "requestid": f"claude-plan-{reading_id}"}


async def sync_reading_to_beeminder(client: Any, goal: Optional[str], history: List[Dict[str, Any]],
                                    reading_id: Any) -> Dict[str, Any]:
    """Push the reading's datapoint to `goal`. Never raises: a Beeminder problem is
    reported in the result and must not fail the recording of the reading itself."""
    if not goal:
        return {"pushed": False, "reason": "CLAUDE_BEEMINDER_GOAL not set"}
    datapoint = beeminder_datapoint(history, reading_id)
    if datapoint is None:
        return {"pushed": False, "reason": "running total unchanged"}
    result = {"pushed": True, "goal": goal, "value": datapoint["value"], "requestid": datapoint["requestid"]}
    try:
        await client.add_datapoint(goal, datapoint["value"], comment=datapoint["comment"],
                                   requestid=datapoint["requestid"])
    except Exception as e:
        status = getattr(e, "status_code", None)
        if status == 422:  # Beeminder's duplicate-requestid answer: this reading is already in
            return {**result, "note": "already recorded"}
        # Type and status only; the response body is not echoed.
        return {"pushed": False, "goal": goal, "error": f"{type(e).__name__} status={status}"}
    return result


class ClaudePlanUsageStore:
    """Neon persistence for claude_plan_usage readings (user-scoped)."""

    def __init__(self, neon_url: Optional[str] = None):
        self.neon_url = neon_url or os.getenv("NEON_DB_URL")
        self._initialized = False

    def _connect(self):
        import psycopg2
        return psycopg2.connect(self.neon_url)

    def init_database(self) -> None:
        if not self.neon_url or self._initialized:
            return
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS claude_plan_usage_readings (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
                        plan TEXT NOT NULL,
                        verified BOOLEAN,
                        windows JSONB NOT NULL,
                        source TEXT NOT NULL,
                        observed_at TIMESTAMPTZ NOT NULL,
                        notes TEXT DEFAULT '',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_claude_plan_usage_user_observed
                    ON claude_plan_usage_readings (user_id, observed_at DESC)
                """)
        self._initialized = True

    def record(self, user_id: str, reading: Dict[str, Any]) -> Dict[str, Any]:
        if not self.neon_url:
            return {"recorded": False, "reason": "NEON_DB_URL not configured"}
        self.init_database()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO claude_plan_usage_readings
                       (user_id, plan, verified, windows, source, observed_at, notes)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (user_id, reading["plan"], reading["verified"], json.dumps(reading["windows"]),
                     reading["source"], reading["observed_at"], reading.get("notes", "")),
                )
                row_id = cur.fetchone()[0]
        return {"recorded": True, "id": row_id}

    def history(self, user_id: str) -> List[Dict[str, Any]]:
        """Every stored reading for the user (id, plan, windows, observed_at), oldest first."""
        if not self.neon_url:
            return []
        self.init_database()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, plan, windows, observed_at FROM claude_plan_usage_readings
                       WHERE user_id = %s ORDER BY observed_at ASC""",
                    (user_id,),
                )
                rows = cur.fetchall()
        out = []
        for rid, plan, windows, observed_at in rows:
            if isinstance(windows, str):
                windows = json.loads(windows)
            out.append({"id": rid, "plan": plan, "windows": windows,
                        "observed_at": _parse_dt(observed_at).isoformat()})
        return out

    def latest(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not self.neon_url:
            return None
        self.init_database()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT plan, verified, windows, source, observed_at, notes
                       FROM claude_plan_usage_readings
                       WHERE user_id = %s ORDER BY observed_at DESC LIMIT 1""",
                    (user_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        plan, verified, windows, source, observed_at, notes = row
        if isinstance(windows, str):
            windows = json.loads(windows)
        return {"plan": plan, "verified": verified, "windows": windows, "source": source,
                "observed_at": _parse_dt(observed_at).isoformat(), "notes": notes or ""}


def make_reading(
    windows: List[Dict[str, Any]],
    plan: str = "ultra",
    verified: Optional[bool] = None,
    source: str = "manual",
    observed_at: Optional[str] = None,
    notes: str = "",
) -> Dict[str, Any]:
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}, got {source!r}")
    observed = _parse_dt(observed_at) or datetime.now(timezone.utc)
    return {
        "plan": plan,
        "verified": infer_verified(windows, verified),
        "windows": windows,
        "source": source,
        "observed_at": observed.isoformat(),
        "notes": notes,
    }
