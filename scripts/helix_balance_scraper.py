"""Helix balance → Beeminder sync (task 588: levers C1b + C1c).

The odometer pipeline (design.md §1, pattern §8 of the article):

    C1a wallet read (scripts/helix_billing.get_balance, 5-min cache, None-safe)
      → Neon helix_balance_log row (every reading, source-tagged; velocity =
        differencing OUR OWN history — never Beeminder, R8)
      → change-gated straight-copy push to goal HELIX_BEEMINDER_GOAL (helix-ml)
      → read-back verification

The push contract (settled at Spec Review, design.md §4):

    value      = round(balance, 2)                      # straight copy, nothing else
    fetch fail → store the row, push NOTHING            # unknown is never $0
    value == last pushed → silence (no rewrite, no dup)
    requestid  = helix-balance-{day}T{HHMM}             # unique per reading; a crash
                # retry of the SAME reading dedupes (BeeminderAPIError 422 = already-in)
    comment    = "Helix balance $498.20 (source=api)"

R8 boundary: the Beeminder goal is a SINK. Position and velocity here come from the
provider + our Neon log only. The one sink reading allowed is `beeminder_required_today`
(the road's tempo), injected by the host into §5.1's merge — tempo, never wealth.

Hand-drive (M3/M4 gate, on the laptop with .env):

    python scripts/helix_balance_scraper.py            # sync once, push if moved
    python scripts/helix_balance_scraper.py --dry-run  # show what would push
    python scripts/helix_balance_scraper.py --force    # push even if unchanged
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# Direct invocation (python scripts/helix_balance_scraper.py) puts scripts/ on
# sys.path, not the repo root — make `from scripts import ...` resolvable.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from zoneinfo import ZoneInfo
    _TZ_DAY = ZoneInfo("US/Eastern")  # reviewstack daystamp convention (D3 default; M2 confirms)
except Exception:  # pragma: no cover - tz data missing (CI containers)
    _TZ_DAY = timezone.utc

try:
    import psycopg2
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    psycopg2 = None
    load_dotenv = None

logger = logging.getLogger(__name__)

GOAL_SLUG = os.getenv("HELIX_BEEMINDER_GOAL", "helix-ml")

# ---- consecutive-failure pulse (R6) — process-local counter, leader runs it ----
_CONSECUTIVE_FETCH_FAILURES = 0

_env_loaded = False


def _ensure_env() -> None:
    global _env_loaded
    if _env_loaded or load_dotenv is None:
        return
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
    _env_loaded = True


def _neon_url() -> Optional[str]:
    _ensure_env()
    return os.getenv("NEON_DB_URL")


def _grant() -> float:
    return float(os.getenv("HELIX_MONTHLY_GRANT", "100"))


def _cap() -> float:
    return float(os.getenv("HELIX_BURN_CAP", "5"))


def _floor() -> float:
    return float(os.getenv("HELIX_BURN_FLOOR", "1"))


def _daystamp(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(timezone.utc)).astimezone(_TZ_DAY).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# C1c — pure scalar merge (design.md §5.1). Pump-side math only; the host
# injects beeminder_required_today (the sink's tempo). Zero-Split-Brain shape.
# ---------------------------------------------------------------------------

def compute_scalars(
    current_balance: Optional[float],
    start_of_day_balance: Optional[float],
    period_end_ts: Optional[float],          # epoch seconds (wallet: subscription_current_period_end)
    *,
    beeminder_required_today: Optional[float] = None,  # host-injected tempo (never wealth)
    grant: Optional[float] = None,
    cap: Optional[float] = None,
    floor: Optional[float] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """The three scalars (R7): live_balance / burned_today / burn_allowance.

    burn_allowance = min(cap, max(pump_pace, beeminder_required_today, floor)).
    The cap is the know-better gate: it refuses top-up day's ≈$100 *number*,
    not the work — the day degrades to an ordinary day. Operator may raise the
    cap; the machine never does.
    """
    now = now or datetime.now(timezone.utc)
    grant = _grant() if grant is None else grant
    cap = _cap() if cap is None else cap
    floor = _floor() if floor is None else floor

    burned: Optional[float] = None
    inflow = False
    if current_balance is not None and start_of_day_balance is not None:
        raw = start_of_day_balance - current_balance
        if raw < 0:  # a top-up inflow is flagged, never absorbed into "burned"
            inflow = True
            burned = 0.0
        else:
            burned = raw

    days_left: Optional[int] = None
    pump_pace: Optional[float] = None
    if period_end_ts:
        days_left = max(1, math.ceil((period_end_ts - now.timestamp()) / 86400))
        pump_pace = grant / days_left

    required_today = max(
        pump_pace if pump_pace is not None else 0.0,
        beeminder_required_today if beeminder_required_today is not None else 0.0,
        floor,
    )
    burn_allowance = min(cap, required_today)

    return {
        "live_balance": current_balance,
        "burned_today": round(burned, 4) if burned is not None else None,
        "burn_allowance": round(burn_allowance, 2),
        "inflow": inflow,
        "days_left_in_period": days_left,
        "pump_pace": round(pump_pace, 2) if pump_pace is not None else None,
        "beeminder_tempo_used": beeminder_required_today,
    }


# ---------------------------------------------------------------------------
# Neon helpers (module-level so tests monkeypatch them; psycopg2 is sync)
# ---------------------------------------------------------------------------

def _fetch_last_ok_row(user_id: str) -> Optional[Dict[str, Any]]:
    url = _neon_url()
    if not url or psycopg2 is None:
        return None
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ts, day, balance, pushed_value FROM helix_balance_log "
                "WHERE user_id = %s AND fetch_status = 'ok' ORDER BY ts DESC LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {"ts": row[0], "day": row[1], "balance": float(row[2]),
            "pushed_value": float(row[3]) if row[3] is not None else None}


def _fetch_start_of_day_balance(user_id: str, day: str) -> Optional[float]:
    """First ok reading with day == today; else the newest ok reading before today."""
    url = _neon_url()
    if not url or psycopg2 is None:
        return None
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT balance FROM helix_balance_log "
                "WHERE user_id = %s AND fetch_status = 'ok' AND day = %s ORDER BY ts ASC LIMIT 1",
                (user_id, day),
            )
            row = cur.fetchone()
            if row:
                return float(row[0])
            cur.execute(
                "SELECT balance FROM helix_balance_log "
                "WHERE user_id = %s AND fetch_status = 'ok' AND day < %s ORDER BY ts DESC LIMIT 1",
                (user_id, day),
            )
            row = cur.fetchone()
    return float(row[0]) if row else None


def _insert_row(user_id: str, *, day: str, balance: Optional[float], delta: Optional[float],
                source: str, fetch_status: str, inflow: bool) -> int:
    url = _neon_url()
    if not url or psycopg2 is None:
        raise RuntimeError("NEON_DB_URL not set — cannot log the reading (R2)")
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO helix_balance_log (user_id, day, balance, delta, source, fetch_status, inflow) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (user_id, day, balance, delta, source, fetch_status, inflow),
            )
            rid = cur.fetchone()[0]
            conn.commit()
    return rid


def _mark_pushed(row_id: int, pushed_value: float) -> None:
    url = _neon_url()
    if not url or psycopg2 is None:
        return
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE helix_balance_log SET pushed_value = %s WHERE id = %s",
                        (pushed_value, row_id))
            conn.commit()


def has_pending_requests(user_id: str) -> bool:
    """Android hook: any request newer than its processed_at?"""
    url = _neon_url()
    if not url or psycopg2 is None:
        return False
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM helix_balance_requests "
                "WHERE user_id = %s AND (processed_at IS NULL OR requested_at > processed_at) LIMIT 1",
                (user_id,),
            )
            return cur.fetchone() is not None


def _mark_requests_processed(user_id: str) -> None:
    url = _neon_url()
    if not url or psycopg2 is None:
        return
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE helix_balance_requests SET processed_at = NOW() WHERE user_id = %s",
                        (user_id,))
            conn.commit()


def minutes_since_last_ok(user_id: str) -> Optional[float]:
    """Hours-cadence self-gating for the 15-minute scheduler job."""
    url = _neon_url()
    if not url or psycopg2 is None:
        return None
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(ts) FROM helix_balance_log WHERE user_id = %s AND fetch_status = 'ok'",
                (user_id,),
            )
            ts = cur.fetchone()[0]
    if not ts:
        return None
    return (datetime.now(timezone.utc) - ts).total_seconds() / 60


# ---------------------------------------------------------------------------
# C1b — the sync lever
# ---------------------------------------------------------------------------

async def sync_helix_balance_to_beeminder(
    user_id: str,
    *,
    source: str = "api",
    force: bool = False,
    dry_run: bool = False,
    beeminder_client=None,
    beeminder_required_today: Optional[float] = None,
) -> Dict[str, Any]:
    """Fetch → log → change-gate → push → read-back. Never raises.

    Returns {ok, balance, pushed, reason, readback?}. A fetch failure is LOGGED
    as fetch_status='failed' (balance NULL) and pushes NOTHING.
    """
    global _CONSECUTIVE_FETCH_FAILURES
    from scripts import helix_billing

    now = datetime.now(timezone.utc)
    day = _daystamp(now)

    wallet = await asyncio.to_thread(helix_billing.get_wallet, True)  # force fresh; M3 gate
    if wallet is None or wallet.get("balance") is None:
        _CONSECUTIVE_FETCH_FAILURES += 1
        row_id = await asyncio.to_thread(
            _insert_row, user_id, day=day, balance=None, delta=None,
            source=source, fetch_status="failed", inflow=False)
        await asyncio.to_thread(_mark_requests_processed, user_id)
        if _CONSECUTIVE_FETCH_FAILURES >= 2:
            await _alert_balance_dark(user_id, _CONSECUTIVE_FETCH_FAILURES)
        return {"ok": False, "balance": None, "pushed": False, "row_id": row_id,
                "reason": "wallet fetch failed (logged; nothing pushed)",
                "consecutive_failures": _CONSECUTIVE_FETCH_FAILURES}
    _CONSECUTIVE_FETCH_FAILURES = 0

    balance = float(wallet["balance"])
    value = round(balance, 2)
    last = await asyncio.to_thread(_fetch_last_ok_row, user_id)
    delta = None if last is None else round(balance - last["balance"], 4)
    inflow = delta is not None and delta > 0
    row_id = await asyncio.to_thread(
        _insert_row, user_id, day=day, balance=balance, delta=delta,
        source=source, fetch_status="ok", inflow=inflow)

    result: Dict[str, Any] = {"ok": True, "balance": balance, "row_id": row_id,
                              "delta": delta, "pushed": False}

    last_pushed = last["pushed_value"] if last else None
    if not force and last_pushed is not None and value == last_pushed:
        result["reason"] = f"unchanged since last push ({value}) — silence (R3)"
        await asyncio.to_thread(_mark_requests_processed, user_id)
        return result

    hhmm = now.strftime("%H%M")
    requestid = f"helix-balance-{day}T{hhmm}"
    comment = f"Helix balance ${value:.2f} (source={source})"

    if dry_run:
        result["reason"] = f"dry-run: would push {value} requestid={requestid}"
        return result

    if beeminder_client is None:
        from mcp_server import get_user_beeminder_client
        beeminder_client = get_user_beeminder_client(user_id)

    goal = os.getenv("HELIX_BEEMINDER_GOAL", GOAL_SLUG)
    try:
        await beeminder_client.add_datapoint(goal, value, comment=comment, requestid=requestid)
        pushed = True
    except Exception as exc:  # BeeminderAPIError
        # 422 = requestid dedupe fired = the same reading is already in (Rust twin
        # semantics, sync-service/src/lib.rs:584-594). Any other error: do NOT mark.
        if getattr(exc, "status_code", None) == 422:
            pushed = True
            result["note"] = "requestid dedupe fired (422) — already in, treated as success"
        else:
            result["reason"] = f"push failed: {exc}"
            await asyncio.to_thread(_mark_requests_processed, user_id)
            return result

    await asyncio.to_thread(_mark_pushed, row_id, value)
    await asyncio.to_thread(_mark_requests_processed, user_id)
    result["pushed"] = True
    result["reason"] = f"pushed {value} to {goal} (requestid={requestid})"

    try:
        dps = await beeminder_client.get_goal_datapoints(goal, count=1)
        if dps:
            result["readback"] = {"value": dps[0].get("value"), "comment": dps[0].get("comment"),
                                  "daystamp": dps[0].get("daystamp")}
    except Exception as exc:
        result["readback"] = {"error": str(exc)}
    return result


# ---------------------------------------------------------------------------
# Scalars exposure (C5b narrator + MCP tool read path)
# ---------------------------------------------------------------------------

def get_helix_scalars_sync(user_id: str,
                           beeminder_required_today: Optional[float] = None) -> Dict[str, Any]:
    """Latest position/velocity/allowance from Neon history + wallet. Scalar-only (R7).

    Sync core (narrator summary is a sync call path); the async wrapper below is
    for the MCP tool. Provenance (R9 spirit): a stale Neon row is LABELLED stale,
    never passed off as live.
    """
    from scripts import helix_billing

    last = _fetch_last_ok_row(user_id)
    wallet = helix_billing.get_wallet()
    balance = float(wallet["balance"]) if wallet and wallet.get("balance") is not None \
        else (last["balance"] if last else None)
    day = _daystamp()
    sod = _fetch_start_of_day_balance(user_id, day)
    period_end = wallet.get("subscription_current_period_end") if wallet else None
    scalars = compute_scalars(balance, sod, float(period_end) if period_end else None,
                              beeminder_required_today=beeminder_required_today)
    if wallet:
        scalars["balance_source"] = "live (wallet)"
    elif last:
        age_min = round((datetime.now(timezone.utc) - last["ts"]).total_seconds() / 60, 1)
        scalars["balance_source"] = f"neon_log (stale {age_min} min) — wallet fetch unavailable"
    else:
        scalars["balance_source"] = "unavailable (no log rows, no wallet)"
    return scalars


async def get_helix_scalars(user_id: str,
                            beeminder_required_today: Optional[float] = None) -> Dict[str, Any]:
    """Async wrapper around get_helix_scalars_sync."""
    return await asyncio.to_thread(get_helix_scalars_sync, user_id, beeminder_required_today)


async def _alert_balance_dark(user_id: str, count: int) -> None:
    """R6 pulse: ≥2 consecutive fetch failures → existing reminder channel, 1/day (walk-monitor pattern)."""
    url = _neon_url()
    if not url or psycopg2 is None:
        return
    try:
        today = datetime.now(timezone.utc).date()
        with psycopg2.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM message_log WHERE date = %s AND type = %s AND user_id = %s LIMIT 1",
                            (today, "helix_balance_dark", user_id))
                if cur.fetchone():
                    return
        from twilio_sender import smart_send_message
        result = smart_send_message(
            f"🌀 Mecris: Helix balance reads failed {count}× in a row. The odometer is "
            "dark — check HELIX_BILLING_API_TOKEN / network.")
        if result.get("sent"):
            with psycopg2.connect(url) as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO message_log (user_id, type, sent_at, compliance_status) "
                                "VALUES (%s, %s, CURRENT_TIMESTAMP, 'sent')",
                                (user_id, "helix_balance_dark"))
                    conn.commit()
    except Exception as exc:  # the pulse alert is best-effort, never fatal
        logger.warning("helix balance dark alert failed: %s", exc)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Hand-drive the Helix balance → Beeminder sync")
    parser.add_argument("--user-id",
                        default=os.getenv("MECRIS_USER_ID") or os.getenv("DEFAULT_USER_ID", "yebyen@gmail.com"))
    parser.add_argument("--force", action="store_true", help="push even if unchanged")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--scalars", action="store_true", help="print scalars only, no write")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    async def _run():
        if args.scalars:
            return await get_helix_scalars(args.user_id)
        return await sync_helix_balance_to_beeminder(
            args.user_id, force=args.force, dry_run=args.dry_run)

    print(json.dumps(asyncio.run(_run()), indent=2, default=str))


if __name__ == "__main__":
    main()
