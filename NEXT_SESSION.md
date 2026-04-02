# Next Session: Goal 1 Phase 2 — Ghost Archivist Session Prototype

## Current Status (Thursday, April 2, 2026 — session 9)
- **Ghost Presence Module COMPLETE** ✓: `ghost/presence.py` extracted with `acquire_lock()`, `release_lock()`, `check_presence()`, and `presence_lock()` context manager.
- **16/16 presence tests PASS**: Full acquire/release lifecycle, stale lock detection, custom TTL, concurrent session deferral, and exception-safe context manager.
- **CLI refactored**: `cli/main.py::run_presence()` now delegates to `ghost.presence` instead of inline file ops.
- **Repos**: yebyen/mecris is 1 commit ahead of origin/main (committed 3f06f2b; push handled by workflow).

## Verified This Session
- [x] **ghost/presence.py**: `acquire_lock()` / `release_lock()` / `check_presence()` / `presence_lock()` all implemented and tested.
- [x] **Stale lock detection**: Locks older than 30 minutes are treated as "human gone" (configurable via `ttl` param).
- [x] **Context manager**: `presence_lock()` auto-releases even on exception.
- [x] **Concurrent deferral**: Test proves second session detects active lock and gets `human_present=True`.
- [x] **CLI integration**: `cli presence check|take|release` uses module, no duplication.

## Pending Verification (Next Session)

### HIGHEST PRIORITY: Goal 1 Phase 2 — Archivist Ghost Session
- **Foundation**: `ghost/presence.py` is ready. Next step: wire it into the actual bot/cron workflow.
- **Task**: Create `ghost/archivist.py` that:
  1. Calls `check_presence()` at startup — if `human_present=True`, print "yielding" and exit 0.
  2. Does a basic "pulse" (reads `get_narrator_context` or similar MCP call).
  3. Logs to `logs/ghost_archivist.log` with timestamp.
- **Goal**: A cron-invocable script that autonomously monitors system pulse without conflicting with human sessions.

### Nag Ladder: Tier 2 message content (kingdonb/mecris#139)
- Tier 2 currently sends `use_template: False` with a generic `fallback_message`.
- Decide on actual coaching copy for escalated walk/Beeminder alerts.

### PR-Test Fix (kingdonb/mecris#163)
- Blocked on Kingdon updating `MECRIS_BOT_CLASSIC_PAT` with `workflow` scope.
- No action needed from bot side until token is updated.

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted. Use targeted `include_pattern` or `dir_path`.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **Nag Ladder tier semantics**:
    - Tier 1: WhatsApp Template (Gentle)
    - Tier 2: WhatsApp Freeform (Escalated, 6h idle)
    - Tier 3: WhatsApp High Urgency (Critical, <2h runway)
- **Global Rate Limit**: 2 messages per hour across ALL channels.
- **ghost/ package**: New top-level package; import as `from ghost.presence import ...` with `PYTHONPATH=.`.
