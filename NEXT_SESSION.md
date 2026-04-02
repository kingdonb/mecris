# Next Session: Nag Ladder Tier 2 — Decide Coaching Copy for Escalated Alerts

## Current Status (Thursday, April 2, 2026 — session 11)
- **Goal 1 Phase 3 COMPLETE** ✓: `ghost/archivist.py` is now registered as `auto_archivist_{user_id}` in `MecrisScheduler._start_leader_jobs` / `_stop_leader_jobs`, firing every 15 minutes.
- **13/13 archivist tests PASS**: includes 3 new `TestGlobalArchivistJob` tests (leader fires, non-leader skips, exception handling).
- **16/16 presence tests PASS**: `tests/test_ghost_presence.py` unaffected.
- **Repos**: yebyen/mecris is ahead of kingdonb/mecris (sessions 9+10+11 not yet upstreamed; push handled by workflow).

## Verified This Session
- [x] **_global_archivist_job**: calls `ghost.archivist.run()` when `is_leader=True`, returns early when `is_leader=False`.
- [x] **Error handling**: exceptions are caught and logged, not raised (scheduler must not crash on archivist failure).
- [x] **Leader job lifecycle**: job added in `_start_leader_jobs` (`minutes=15`, `id=auto_archivist_{user_id}`), removed in `_stop_leader_jobs`.
- [x] **Scheduler election counts updated**: `test_scheduler_election.py` now expects 5 leader jobs (was 4).

## Pending Verification (Next Session)

### HIGHEST PRIORITY: Nag Ladder Tier 2 Message Content (kingdonb/mecris#139)
- Tier 2 currently sends `use_template: False` with a generic `fallback_message`.
- Decide on actual coaching copy for escalated walk/Beeminder alerts (6h idle tier).
- Check `services/coaching_service.py` and `services/reminder_service.py` for where Tier 2 content is specified.
- Write/update the coaching message; add or update tests if the copy is hardcoded.

### PR-Test Fix (kingdonb/mecris#163)
- Blocked on Kingdon updating `MECRIS_BOT_CLASSIC_PAT` with `workflow` scope.
- No action needed from bot side until token is updated.

### Ghost Archivist Live Validation (carry-forward)
- The archivist job fires every 15 minutes when `MecrisScheduler` is the leader.
- Can only be validated in a live environment (Neon DB, running MCP server).
- When next doing a live session, confirm `logs/ghost_archivist.log` accumulates PULSE entries.

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted. Use targeted `include_pattern` or `dir_path`.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **Nag Ladder tier semantics**:
    - Tier 1: WhatsApp Template (Gentle)
    - Tier 2: WhatsApp Freeform (Escalated, 6h idle)
    - Tier 3: WhatsApp High Urgency (Critical, <2h runway)
- **Global Rate Limit**: 2 messages per hour across ALL channels.
- **ghost/ package**: Top-level package; import as `from ghost.presence import ...` or `from ghost.archivist import run` with `PYTHONPATH=.`.
- **Test command**: `PYTHONPATH=. python3 -m pytest` (`.venv/bin/pytest` may not exist in CI; use `python3 -m pytest` directly).
- **Scheduler election tests**: `tests/test_scheduler_election.py` requires psycopg2 — these fail in the bare CI environment. Pre-existing condition, not a regression.
