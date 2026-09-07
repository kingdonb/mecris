---

okf_version: "0.2"
concept_id: "2026/09/06/ghost/heartbeat/validation"
type: "Decision"
status: "stable"
title: "Ghost Archivist Heartbeat End-to-End Validation and Operational Diagnosis"
inbound: ["decisions/2026-09-06-ghost-heartbeat-restoration", "architecture/ghost-heartbeat-restoration"]
outbound: ["decisions/2026-09-06-ghost-heartbeat-restoration", "architecture/ghost-heartbeat-restoration"]

  relationships:
    - target: "decisions/2026-09-06-ghost-heartbeat-restoration"
      description: "validates the REST API mechanism proposed in restoration decision"
    - target: "architecture/ghost-heartbeat-restoration"
      description: "references architectural mechanism"
---

# Ghost Archivist Heartbeat End-to-End Validation

## Operational Context
Following the implementation of the REST API heartbeat mechanism in commit `e000b141` / PR #297, an end-to-end investigation was conducted to determine why the ghost archivist was reported silent for ~407 hours in `narrator_context` and why it did not fire automatically.

## Findings & Root Cause Analysis

1. **Authentication Token Lifecycle (`credentials.json`)**:
   - The `/heartbeat` POST endpoint requires authenticated access (`Depends(get_authorized_user)`).
   - The user's access token stored in `~/.mecris/credentials.json` had expired (`Signature has expired`, diff -40914s).
   - Calling `python -m cli.main login` performed a silent refresh using the stored refresh token against Pocket ID, successfully restoring valid credentials.
   - When called with the refreshed bearer token, `POST http://localhost:8080/heartbeat` responded with HTTP 200 `{"status":"success","mcp_server_active":true}` and updated `scheduler_election` for role `active_ghost`.

2. **Presence Table Persistence**:
   - Direct store inspection verified that `NEON_DB_URL` is configured in the environment / `.env`.
   - Updating `store.upsert(user_id, StatusType.ACTIVE_GHOST, source="archivist")` immediately updated `last_ghost_activity` in the Neon DB `presence` table.
   - `mecris_get_narrator_context()` immediately reflected this live state:
     - `👻 Ghost Heartbeat: Bot was active 0m ago.` (clearing the 407h silence warning).
     - `last_ghost_activity`: updated to current UTC timestamp.

3. **Autonomous Execution Rhythm & The 12-Hour Cooldown**:
   - Per Ghost Archivist specification `SYS-001` and `ghost/archivist_logic.py`, `should_ghost_wake_up()` enforces `GHOST_COOLDOWN_SECONDS = 12 * 3600` (12 hours).
   - The scheduler registers `auto_archivist_{user_id}` on a 15-minute interval in `apscheduler_jobs` (`next_run_time` active).
   - Every 15 minutes, the scheduled job invokes `ghost.archivist.run()`.
   - When human presence is detected or when less than 12 hours have elapsed since `last_ghost_activity`, the archivist intentionally enters sleep/yield mode (`Sleep heuristic active`).
   - The archivist is a **reality enforcer**, not a continuous poller; when Beeminder and Clozemaster goals are fully accounted and within the 12-hour window, remaining idle is by design.

4. **Port Configuration Discrepancy**:
   - The local running MCP server serves HTTP on port `8080`.
   - The fallback URL in `ghost/archivist_logic.py` targets port `8000`. When run in an environment without direct DB access, `MECRIS_MCP_URL` or an updated default is required to reach the REST heartbeat on port `8080`.

**Generated**: { by: "agent/gpt-5.6-sol", at: "2026-09-06T22:45:00Z" }
**Sources**: `/tmp/agentworld_prompt.md`, `ghost/archivist_logic.py`, `ghost/presence.py`, `scheduler.py`, `logs/mecris_server.log`, live Neon DB queries

## Related Concepts
- [Restore Ghost Heartbeat by Porting Archivist to REST API (Multi-Tenant/API-First)](2026-09-06-ghost-heartbeat-restoration.md): Validates the REST API mechanism proposed in restoration decision.
- [Ghost Heartbeat Restoration via REST API (Multi-Tenant/API-First)](../architecture/ghost-heartbeat-restoration.md): References architectural mechanism.
