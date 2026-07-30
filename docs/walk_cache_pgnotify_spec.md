# Walk Cache Invalidation via pg_notify — Priority 3 Spec

## Problem Statement

`get_cached_daily_activity("bike")` in `mcp_server.py` caches "no walk today" for **15 minutes** (TTL). When `WalkHeuristicsWorker` uploads a walk via `/walks` endpoint, the cache isn't invalidated → Android shows 0 steps for up to 15 min after successful sync.

Current flow:
```
Android Health Connect → WalkHeuristicsWorker (15min) → POST /walks → Neon walk_inferences (status='logging')
                                                            ↓
                                          Leader _global_walk_sync_job (15min) → Beeminder
                                                            ↓
                                                    walk_inferences.status = 'logged'
```

Cache invalidation only happens on TTL expiry.

---

## Solution: PostgreSQL NOTIFY/LISTEN

### 1. Database Migration

```sql
-- migration: add_walk_invalidation_trigger.sql
CREATE OR REPLACE FUNCTION notify_walk_change()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_notify(
    'walk_inferences_change',
    json_build_object('user_id', NEW.user_id, 'op', TG_OP)::text
  );
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS walk_inferences_change_trigger ON walk_inferences;
CREATE TRIGGER walk_inferences_change_trigger
AFTER INSERT OR UPDATE ON walk_inferences
FOR EACH ROW EXECUTE FUNCTION notify_walk_change();
```

### 2. Python Listener — `services/walk_cache_listener.py`

```python
"""
Background task: LISTEN walk_inferences_change → evict daily_activity_cache for that user.
Runs in MCP server process (same event loop).
"""
import asyncio
import json
import logging
import os
import asyncpg
from mcp_server import daily_activity_cache  # module-level cache dict

logger = logging.getLogger("mecris.walk_cache_listener")

async def start_walk_cache_listener():
    dsn = os.getenv("NEON_DB_URL").replace("postgresql://", "postgres://")
    conn = await asyncpg.connect(dsn)
    await conn.add_listener("walk_inferences_change", _on_walk_change)
    logger.info("Walk cache listener started on channel 'walk_inferences_change'")
    # Keep connection alive
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await conn.remove_listener("walk_inferences_change", _on_walk_change)
        await conn.close()

def _on_walk_change(conn, pid, channel, payload):
    try:
        data = json.loads(payload)
        user_id = data["user_id"]
        # Cache key format: "{user_id}:bike:{today_eastern_iso}"
        from services.timezone_service import today_eastern
        today = today_eastern().isoformat()
        key = f"{user_id}:bike:{today}"
        if key in daily_activity_cache:
            del daily_activity_cache[key]
            logger.info(f"Evicted walk cache for {key}")
    except Exception as e:
        logger.error(f"Walk cache invalidation failed: {e}")
```

### 3. Integration in `mcp_server.py`

```python
# Top of file (after imports)
from services.walk_cache_listener import start_walk_cache_listener

# In main() / lifespan startup (after scheduler.start()):
asyncio.create_task(start_walk_cache_listener())
```

### 4. Fallback Safety

- Listener crashes → logged, cache falls back to 15-min TTL (existing behavior)
- If `asyncpg` unavailable → listener not started, TTL-only mode
- No schema changes to `walk_inferences` table

---

## Acceptance Criteria

1. Migration applies cleanly to Neon (run via `psql $NEON_DB_URL -f migration.sql`).
2. After `POST /walks` inserts row with `status='logging'`, `get_cached_daily_activity("bike")` returns fresh data on **next call** (no 15-min wait).
3. Listener survives MCP server restart (reconnects on startup).
4. No regression: cache still works when listener is down (TTL fallback).
5. Unit test: mock `pg_notify` → verify cache key deleted.

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `migrations/add_walk_invalidation_trigger.sql` | New |
| `services/walk_cache_listener.py` | New |
| `mcp_server.py` | Add import + `asyncio.create_task(start_walk_cache_listener())` in startup |
| `tests/test_walk_cache_listener.py` | New (mock asyncpg + NOTIFY) |

---

## Out of Scope

- Invalidating `/languages` or `/aggregate-status` caches (different keys, separate PR).
- Android-side cache (Android relies on server response).
- Beeminder sync timing — unchanged.