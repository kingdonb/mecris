# Next Session: Goal 1 Phase 3 — Wire Ghost Archivist into Cron/Bot Workflow

## Current Status (Thursday, April 2, 2026 — session 10)
- **Ghost Archivist Module COMPLETE** ✓: `ghost/archivist.py` implemented with `run()`, `pulse()`, and `_write_log()`.
- **10/10 archivist tests PASS**: YIELD path (human present), PULSE online, PULSE offline, log file creation, exit codes, timestamp format.
- **Smoke test verified**: `python ghost/archivist.py` with no lock active logs `[PULSE] mcp=offline` correctly (server not running in CI).
- **Repos**: yebyen/mecris is ahead of kingdonb/mecris (sessions 9+10 not yet upstreamed; push handled by workflow).

## Verified This Session
- [x] **ghost/archivist.py**: `run()` checks presence, yields (exit 0 + YIELD log) if human detected, otherwise calls `pulse()` and logs PULSE entry.
- [x] **pulse()**: probes `{MECRIS_MCP_URL}/health`, returns `{"status": "online", "server_ts": ...}` or `{"status": "offline", "error": ...}`.
- [x] **Log format**: `{ISO-8601 UTC} [{YIELD|PULSE}] {detail}` appended to `logs/ghost_archivist.log`.
- [x] **Log dir auto-created**: `os.makedirs` ensures the log path exists even if `logs/` subdir doesn't exist.
- [x] **Environment overrides**: `GHOST_LOCK_PATH`, `GHOST_LOG_PATH`, `MECRIS_MCP_URL` all respected.

## Pending Verification (Next Session)

### HIGHEST PRIORITY: Goal 1 Phase 3 — Cron Integration
- **Foundation**: `ghost/archivist.py` is ready and tested. Next step: register it as a cron entry.
- **Task**: Add `ghost/archivist.py` to the scheduler or cron infrastructure:
  1. Check `scheduler.py` for how other cron jobs are registered.
  2. Add an archivist job that fires every N minutes (15? 30?) when no human session is active.
  3. Verify that `logs/ghost_archivist.log` accumulates entries when the scheduler runs.
- **Goal**: A fully autonomous ghost session that logs pulse entries on a schedule and defers to human sessions.

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
- **ghost/ package**: Top-level package; import as `from ghost.presence import ...` or `from ghost.archivist import run` with `PYTHONPATH=.`.
- **Test command**: `PYTHONPATH=. python3 -m pytest` (`.venv/bin/pytest` may not exist in CI; use `python3 -m pytest` directly).
