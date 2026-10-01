"""
Beeminder road math — due-today computation from a goal JSON.

Pure functions, no I/O, no third-party imports. Mirrors road_value_today() /
beeminder_due_today() in mecris-go-spin/sync-service/src/lib.rs (Rust twin);
keep in lockstep (task 000617).

Semantics (task 000617 design):
- Timezone is hardcoded America/New_York: the system axiomatically has one
  user and that is their timezone (operator ruling 2026-10-01).
- ``fullroad`` rows are [daystamp, value, rate]; daystamp is YYYYMMDD (int or
  string, with or without dashes), value is the road value at the END of that
  day, rate is per-day.
- yaw = -1 (do-less, e.g. reviewstack): the good side is BELOW the road, so
  the amount owed today is curval - road_today.
  yaw = +1 (do-more): the good side is ABOVE the road, so it is
  road_today - curval.
- Fractional demands ceil upward: owing 0.4 of a unit still means doing 1 —
  flooring would leave the datapoint above a do-less road (derail).
- When direction (yaw) is missing or the road can't be determined, due is 0:
  never fabricate a demand from data we can't interpret.
"""

import logging
import math
from datetime import date, datetime
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("mecris.beeminder.road")

GOAL_TIMEZONE = ZoneInfo("America/New_York")


def goal_daystamp(now: Optional[datetime] = None) -> int:
    """Today's daystamp (YYYYMMDD int) in the goal timezone."""
    day = (now or datetime.now()).astimezone(GOAL_TIMEZONE).date()
    return day.year * 10000 + day.month * 100 + day.day


def _parse_daystamp(raw: Any) -> Optional[int]:
    """Accept 20261001 (int), '20261001', or '2026-10-01'; else None."""
    try:
        return int(str(raw).replace("-", ""))
    except (ValueError, TypeError):
        return None


def _daystamp_to_date(daystamp: int) -> Optional[date]:
    """YYYYMMDD int -> date; None if not a real calendar day.

    Daystamps never subtract linearly (20261001 - 20260930 == 71), so any
    elapsed-day math goes through real dates.
    """
    try:
        return date(daystamp // 10000, (daystamp // 100) % 100, daystamp % 100)
    except ValueError:
        return None


def road_value_today(fullroad: Optional[List[Any]], daystamp: Optional[int] = None) -> Optional[float]:
    """
    Bright Red Line value at the end of ``daystamp`` (goal timezone), taken
    from the goal JSON's ``fullroad`` array of [daystamp, value, rate] rows.

    - Exact-day match preferred (fullroad has daily granularity within the
      road's span; today's row exists for any road that spans today).
    - Before the first row: the first row's value.
    - After the last row: extrapolate the last row's value by its per-day
      rate (roads continue at their final rate indefinitely).
    - Rows that don't parse are skipped; returns None if nothing usable
      remains.
    """
    if not fullroad:
        return None
    day = daystamp if daystamp is not None else goal_daystamp()
    rows: List[tuple] = []
    for row in fullroad:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        d = _parse_daystamp(row[0])
        if d is None:
            continue
        try:
            v = float(row[1])
        except (ValueError, TypeError):
            continue
        rows.append((d, v, row[2] if len(row) > 2 else None))
    if not rows:
        return None
    rows.sort(key=lambda r: r[0])
    if day < rows[0][0]:
        return rows[0][1]
    for (d, v, _rate) in rows:
        if d == day:
            return v
    last_day, last_val, last_rate = rows[-1]
    try:
        if last_rate is not None:
            last_date = _daystamp_to_date(last_day)
            today_date = _daystamp_to_date(day)
            if last_date is not None and today_date is not None:
                return last_val + float(last_rate) * (today_date - last_date).days
    except (ValueError, TypeError):
        pass
    return last_val


def beeminder_due_today(yaw: Optional[float], curval: Any, road_today: Optional[float]) -> int:
    """
    Units (cards) owed TODAY so the end-of-day value lands on the good side
    of the Bright Red Line. Already net of completions: as cards are done and
    synced, ``curval`` falls, so subtracting ``daily_completions`` again
    downstream would double-count — combine with the pump at the *remaining*
    level: effective_remaining = max(pump_remaining, beeminder_due_today).

    Cross-check canary: when safebuf >= 1 this must compute to ~0; a positive
    due alongside a positive safebuf means the road parse or sign convention
    is wrong (witness-driven debugging hook).
    """
    if road_today is None or yaw is None:
        return 0
    try:
        cur = float(curval)
        road = float(road_today)
        direction = int(yaw)
    except (ValueError, TypeError):
        return 0
    raw = (cur - road) if direction < 0 else (road - cur)
    if raw <= 0:
        return 0
    return int(math.ceil(raw - 1e-9))
