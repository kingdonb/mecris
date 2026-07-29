"""
Walk Cache Listener — Invalidation via PostgreSQL NOTIFY/LISTEN.

Listens for `walk_inferences_change` notifications and evicts the
`daily_activity_cache` entry for the affected user/date.
Runs as a background task in the MCP server process.
"""
import asyncio
import json
import logging
import os
from typing import Optional

import asyncpg

from services.timezone_service import today_eastern

logger = logging.getLogger("mecris.walk_cache_listener")

# Module-level cache reference (populated by mcp_server on startup)
daily_activity_cache: Optional[dict] = None


def set_cache_reference(cache: dict):
    """Called by mcp_server at startup to inject the cache dict."""
    global daily_activity_cache
    daily_activity_cache = cache


async def start_walk_cache_listener() -> asyncio.Task:
    """
    Start the LISTEN task. Returns the asyncio Task for lifecycle management.
    Caller should await/cancel on shutdown.
    """
    dsn = os.getenv("NEON_DB_URL")
    if not dsn:
        logger.warning("NEON_DB_URL not set — walk cache listener disabled")
        return None

    # asyncpg expects postgresql:// not postgres://
    if dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql://", 1)

    async def _listener_task():
        conn = None
        try:
            conn = await asyncpg.connect(dsn)
            await conn.add_listener("walk_inferences_change", _on_walk_change)
            logger.info("Walk cache listener started on channel 'walk_inferences_change'")

            # Keep connection alive
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Walk cache listener cancelled")
            raise
        except Exception as e:
            logger.error(f"Walk cache listener error: {e}")
        finally:
            if conn:
                try:
                    await conn.remove_listener("walk_inferences_change", _on_walk_change)
                except Exception:
                    pass
                await conn.close()

    return asyncio.create_task(_listener_task())


def _on_walk_change(conn: asyncpg.Connection, pid: int, channel: str, payload: str):
    """Callback fired when walk_inferences row is inserted/updated."""
    try:
        data = json.loads(payload)
        user_id = data.get("user_id")
        if not user_id:
            return

        # Cache key format: "{user_id}:bike:{today_eastern_iso}"
        today = today_eastern().isoformat()
        key = f"{user_id}:bike:{today}"

        if daily_activity_cache and key in daily_activity_cache:
            del daily_activity_cache[key]
            logger.info(f"Evicted walk cache for {key} (op: {data.get('op')})")
    except Exception as e:
        logger.error(f"Walk cache invalidation failed: {e}")