# Spec: The Ghost Archivist (Goal 1.1)

The **Ghost Archivist** is the first implementation of an autonomous "Ghost Session." Its purpose is to ensure that Mecris observes the passage of time and records daily snapshots even if the human user does not interact with the system (app or CLI) for 24+ hours.

## 1. Core Objectives
- **Persistence**: Ensure Beeminder data (via Cloud Sync) continues to flow even if the Android app is uninstalled or inactive.
- **Observability**: Maintain a continuous `session_history` in Neon for long-term momentum analysis.
- **Autonomous Presence**: Verify the `presence.lock` mechanism and system heartbeat logic.

## 2. Trigger Logic (The "Wake-Up" Heuristic)
The Ghost Archivist does NOT poll constantly. It uses the `scheduler_election` table in Neon to decide when to act.

1. **Leader Check**: The Archivist only runs on the instance currently elected as the MCP Leader.
2. **Presence Check**: It checks the `presence` table for the target `user_id`.
3. **Ghost Activation**: If `presence_status == 'silent'` (no human activity for > 12 hours) AND it is currently between 10:00 PM and 11:59 PM Eastern:
   - The Ghost spawns a "Self-Sync" session.
   - It calls `trigger_language_sync` to ensure Beeminder accurately reflects the growing Clozemaster review backlog (as cards age). This explicitly makes the user *less safe* from derailment, keeping the pressure on when they are inactive. It does *not* push 0.0 walk data (Beeminder naturally derails inactive walk goals).
   - It records a log entry: `[GHOST] Archivist performed automated end-of-day sync for user X.`

## 3. Implementation Plan

### Phase A: The `presence` Table (Schema)
Update Neon to track presence specifically:
```sql
CREATE TABLE IF NOT EXISTS user_presence (
    user_id TEXT PRIMARY KEY,
    last_human_activity TIMESTAMPTZ,
    last_ghost_activity TIMESTAMPTZ,
    status TEXT -- 'active_human', 'active_ghost', 'silent'
);
```

### Phase B: The `mecris internal presence` Handle
Add a CLI handle to the `mecris` tool that allows an instance to report its "type" (Human vs Ghost).

### Phase C: The Archivist Loop
Add a new background job to `scheduler.py`: `archivists_round_robin()`.
- Runs every 4 hours.
- If it's late in the day and the human is silent, it performs the "Archival Turn."

## 4. Risks & Mitigations
- **Double-Sync**: The leader election mechanism prevents two ghosts from syncing the same user.
- **Budget Creep**: Ghost turns are strictly metered by the `BudgetGovernor` to prevent runaway API spend.

---
*Created: Saturday, April 4, 2026*
