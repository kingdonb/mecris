# Next Session: Resolve Review Pump Calculation Accuracy (Issue #6)

## Current Status (2026-03-27)
- **Android Sync Verified**: Background and manual failover sync confirmed working via Beeminder (Issue #3) ✅
- **Multiplier Persistence Verified**: App-set multipliers (2.0 Arabic, 5.0 Greek) persisted correctly in Neon (Issue #3) ✅
- **Familiar ID Verified**: `resolve_user_id` added to all core services; `yebyen` maps correctly to UUID in MCP (Issue #3) ✅
- **Bot Loop**: Four-skill loop (orient/plan/archive/pr-test) is stable and running 8x daily upstream.

## Verified This Session
- [x] Android Failover Sync trigger (correct Beeminder comment format)
- [x] Multiplier Lever persistence (Neon DB query confirm)
- [x] MCP `familiar_id` resolution for `yebyen` across `NeonSyncChecker` and `GroqOdometerTracker`
- [x] Multipliers correctly reflected in `get_language_velocity_stats`: 2.0x Arabic, 5.0x Greek

## Pending Verification (Next Session)
- **Review Pump Calculation (Issue #6)**: Audit and fix the calculation logic to ensure it correctly handles the distinction between **Points** and **Cards**. The `reviewstack` goal must remain a card count (driving the physical backlog to zero), while parallel goals track points. Ensure the Pump's "Target Flow Rate" is expressed in the correct unit for the specific goal it's monitoring.
- **Goal Alignment**: Ensure that for card-based goals like `reviewstack`, the Pump isn't inadvertently using point-based completion rates to signal a "Laminar" state.

## Infrastructure Notes
- Python MCP server now has internal `resolve_user_id` logic to handle familiar aliases.
- Cloud Cron is still **DISABLED** in `spin.toml`.
- Skills (orient/plan/archive/pr-test) now synchronized between local `.claude/skills` and upstream `.github/skills`.
