"""
HealthChecker — reads scheduler_election table and returns per-process liveness status.
Implements the Python side of kingdonb/mecris#97 (Unified heartbeat and health visibility).

Status comes from the shared role registry in contracts/pulse_roles.json (#346),
not from a flat 90-second window. The pure helpers below (classify_role,
pick_newest_rows) are also what mcp_server.fetch_system_pulse uses, so the two
Python pulse builders cannot disagree.
"""
import json
import logging
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, List, Optional, Sequence

logger = logging.getLogger("mecris.services.health")

PULSE_ROLES_FILE = Path(__file__).resolve().parents[1] / "contracts" / "pulse_roles.json"

# Limits for active_ghost while MECRIS_GHOST_ENABLED is set. The contract only
# defines the paused lifecycle (#359 keeps the ghost off); these match the old
# narrator's 120-minute "bot was active" threshold.
GHOST_ENABLED_LIMITS = {"healthy_under": 120, "degraded_under": 240}

# Stand-in age for a row with no heartbeat at all.
NEVER_MINUTES = 10 ** 7


@lru_cache(maxsize=1)
def load_pulse_roles() -> Dict[str, Any]:
    """The pulse role registry (contracts/pulse_roles.json)."""
    return json.loads(PULSE_ROLES_FILE.read_text())


def ghost_enabled() -> bool:
    """True when MECRIS_GHOST_ENABLED is set to a truthy value (default off, #359)."""
    return os.getenv("MECRIS_GHOST_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def whole_minutes(value: Any) -> int:
    """floor(minutes), as every arm counts ages (contracts/README.md); None is 'never'."""
    if value is None:
        return NEVER_MINUTES
    try:
        return math.floor(float(value))
    except (TypeError, ValueError):
        return NEVER_MINUTES


def _timed_status(minutes: int, healthy_under: int, degraded_under: int) -> str:
    if minutes < healthy_under:
        return "healthy"
    if minutes < degraded_under:
        return "degraded"
    return "offline"


def classify_role(role: str, minutes: Any, table: Optional[Dict[str, Any]] = None,
                  ghost: Optional[bool] = None) -> Dict[str, Any]:
    """Return {visible, display, status} for one role at an age in minutes."""
    table = table or load_pulse_roles()
    ghost = ghost_enabled() if ghost is None else ghost
    mins = whole_minutes(minutes)
    entry = table["roles"].get(role)
    if entry is None:
        unlisted = table["unlisted_roles"]
        if mins >= unlisted["show_under"]:
            return {"visible": False}
        return {"visible": True, "display": (role or "unknown").replace("_", " ").upper(),
                "status": unlisted["status"]}
    lifecycle = entry["lifecycle"]
    if lifecycle == "retired":
        return {"visible": False}
    if lifecycle == "paused":
        if role == "active_ghost" and ghost:
            return {"visible": True, "display": entry["display"],
                    "status": _timed_status(mins, **GHOST_ENABLED_LIMITS)}
        return {"visible": True, "display": entry["display"], "status": "paused"}
    return {"visible": True, "display": entry["display"],
            "status": _timed_status(mins, entry["healthy_under"], entry["degraded_under"])}


def pick_newest_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One row per role: the newest heartbeat wins, the user's own row on a tie.

    Each row needs 'role', 'minutes' (raw, unfloored age) and 'own'. Order of
    first appearance is kept, so a query ordered by heartbeat stays ordered.
    """
    best: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in rows:
        role = row["role"]
        age = NEVER_MINUTES if row.get("minutes") is None else float(row["minutes"])
        key = (age, not row.get("own", False))
        if role not in best:
            order.append(role)
            best[role] = {**row, "_key": key}
        elif key < best[role]["_key"]:
            best[role] = {**row, "_key": key}
    winners = []
    for role in order:
        row = dict(best[role])
        row.pop("_key", None)
        winners.append(row)
    return winners


class HealthChecker:
    """
    Queries the scheduler_election table to report liveness for all registered processes
    (Python MCP server, Android client, Spin cloud). Returns one dict per visible role,
    each with: role, display, status, minutes_since, process_id, last_heartbeat (ISO
    string), is_active (status == healthy), last_status, last_error, intent.
    """

    def __init__(self):
        self.neon_url = os.getenv("NEON_DB_URL")

    def get_process_statuses(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch rows from scheduler_election for user_id (or global rows where user_id IS NULL)
        and classify them with contracts/pulse_roles.json.

        Includes last_status, last_error, and intent columns when present (migration v8+).
        Falls back gracefully if columns don't exist yet (pre-migration environments).
        """
        if not self.neon_url:
            return []

        try:
            import psycopg2
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    # Detect whether observability columns exist (migration v8).
                    cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'scheduler_election'
                          AND column_name IN ('last_status', 'last_error', 'intent')
                    """)
                    obs_cols = {row[0] for row in cur.fetchall()}
                    has_obs = obs_cols >= {"last_status", "last_error", "intent"}

                    obs_select = "last_status, last_error, intent," if has_obs else ""
                    cur.execute(f"""
                        SELECT role, process_id, heartbeat,
                               EXTRACT(EPOCH FROM (NOW() - heartbeat)) / 60 AS minutes_since,
                               {obs_select}
                               user_id IS NOT NULL AS own
                        FROM scheduler_election
                        WHERE user_id = %s OR user_id IS NULL
                        ORDER BY role
                    """, (user_id,))
                    raw = []
                    for row in cur.fetchall():
                        role, process_id, heartbeat, minutes = row[0], row[1], row[2], row[3]
                        if has_obs:
                            last_status, last_error, intent = row[4], row[5], row[6]
                            own = bool(row[7]) if len(row) > 7 else False
                        else:
                            last_status = last_error = intent = None
                            own = bool(row[4]) if len(row) > 4 else False
                        raw.append({
                            "role": role,
                            "process_id": process_id,
                            "heartbeat": heartbeat,
                            "minutes": None if minutes is None else float(minutes),
                            "own": own,
                            "last_status": last_status,
                            "last_error": last_error,
                            "intent": intent,
                        })

            processes = []
            for row in pick_newest_rows(raw):
                verdict = classify_role(row["role"], row["minutes"])
                if not verdict["visible"]:
                    continue
                heartbeat = row["heartbeat"]
                processes.append({
                    "role": row["role"],
                    "display": verdict["display"],
                    "status": verdict["status"],
                    "minutes_since": whole_minutes(row["minutes"]),
                    "process_id": row["process_id"],
                    "last_heartbeat": heartbeat.isoformat() if heartbeat else None,
                    "is_active": verdict["status"] == "healthy",
                    "last_status": row["last_status"],
                    "last_error": row["last_error"],
                    "intent": row["intent"],
                })
            return processes

        except Exception as e:
            logger.error(f"HealthChecker.get_process_statuses failed: {e}")
            raise

    def get_system_health(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Return a summary health dict suitable for surfacing in get_narrator_context or directly.
        leader_process_id is the process named in the leader row, not the caller.
        """
        if not self.neon_url:
            return {"error": "NEON_DB_URL not configured", "processes": []}

        try:
            processes = self.get_process_statuses(user_id)
            any_active = any(p["is_active"] for p in processes)
            leader = next((p for p in processes if p["role"] == "leader"), None)
            return {
                "processes": processes,
                "overall_status": "healthy" if any_active else "degraded",
                "leader_process_id": leader["process_id"] if leader else None,
            }
        except Exception as e:
            return {"error": str(e), "processes": []}
