"""
ghost.archivist — Presence-aware autonomous pulse logger for Mecris.

A cron-invocable script that:
1. Checks presence — yields (exit 0) if a human session is active.
2. Probes the Mecris MCP server for a system pulse.
3. Performs archival sync via archivist_logic if a human is silent.
4. Appends a timestamped log entry to logs/ghost_archivist.log.

Usage::

    python ghost/archivist.py

Environment::

    MECRIS_MCP_URL  — Override MCP server URL (default: http://localhost:8000)
    GHOST_LOCK_PATH — Override presence lock path
    GHOST_LOG_PATH  — Override log file path
"""

import os
import sys
import datetime
import urllib.request
import json
import asyncio
from typing import Optional

from ghost.presence import check_presence, get_neon_store
from ghost.archivist_logic import perform_archival_sync, should_ghost_wake_up

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LOG_PATH = os.path.join(_REPO_ROOT, "logs", "ghost_archivist.log")
DEFAULT_MCP_URL = "http://localhost:8000"


def pulse(mcp_url: str = DEFAULT_MCP_URL) -> dict:
    """
    Probe the MCP server with a lightweight health check.
    """
    try:
        req = urllib.request.Request(
            f"{mcp_url}/health",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return {"status": "online", "server_ts": data.get("timestamp", "?")}
    except Exception as exc:
        return {"status": "offline", "error": str(exc)}


def _write_log(log_path: str, timestamp: str, event: str, detail: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    with open(log_path, "a") as fh:
        fh.write(f"{timestamp} [{event}] {detail}\n")


async def run(
    user_id: Optional[str] = None,
    lock_path: Optional[str] = None,
    log_path: Optional[str] = None,
    mcp_url: Optional[str] = None,
) -> int:
    """
    Main archivist logic. Async-aware.
    """
    _log_path = log_path or os.environ.get("GHOST_LOG_PATH", DEFAULT_LOG_PATH)
    _mcp_url = mcp_url or os.environ.get("MECRIS_MCP_URL", DEFAULT_MCP_URL)
    _lock_path = lock_path or os.environ.get("GHOST_LOCK_PATH") or None

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Presence check — yield if human is active (local lock file)
    status = check_presence(_lock_path)
    if status.human_present:
        msg = f"human_present=True lock_age={status.age_seconds:.0f}s — yielding"
        print(f"[ghost.archivist] {msg}")
        _write_log(_log_path, timestamp, "YIELD", msg)
        return 0

    # 2. Pulse the MCP server
    pulse_result = pulse(_mcp_url)
    if pulse_result["status"] == "online":
        detail = f"mcp=online server_ts={pulse_result['server_ts']}"
    else:
        detail = f"mcp=offline error={pulse_result['error']}"

    _write_log(_log_path, timestamp, "PULSE", detail)
    print(f"[ghost.archivist] pulse logged: {detail}")

    # 3. Autonomous "Wake-Up" Heuristic (Neon-backed)
    if user_id:
        store = get_neon_store()
        if store:
            record = store.get(user_id)
            if record and should_ghost_wake_up(record, datetime.datetime.now(datetime.timezone.utc)):
                print(f"[ghost.archivist] Waking up for archival sync: user={user_id}")
                _write_log(_log_path, timestamp, "WAKE", f"Archival sync triggered for {user_id}")
                await perform_archival_sync(user_id)
            else:
                print(f"[ghost.archivist] Sleep heuristic active for user={user_id}")
        else:
            print(f"[ghost.archivist] Neon store unavailable for user={user_id}")

    return 0


def main():
    """Synchronous entry point for command-line usage."""
    user_id = os.environ.get("MECRIS_USER_ID")
    try:
        return asyncio.run(run(user_id=user_id))
    except KeyboardInterrupt:
        return 1


if __name__ == "__main__":
    sys.exit(main())
