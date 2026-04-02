# Next Session: Ghost Presence Phase 2 — mcp_server.py middleware (kingdonb/mecris#164)

## Current Status (Thursday, April 2, 2026 — session 16)
- **Upstream PR open**: kingdonb/mecris#165 — "feat(nag-ladder): Complete Nag Ladder" (yebyen:main → kingdonb:main). Still awaiting human review + merge.
- **Ghost Presence Phase 1 complete** (commit `2e6e11b`): Neon presence table DDL, `ghost/presence.py` Neon store + POUND_SAND/SOFY state machine, 17 new unit tests — all passing. Plan issue yebyen/mecris#69 closed.
- **kingdonb/mecris#164** (Ghost Presence Neon Evolution): Phase 1 done. Phase 2 remaining: `mcp_server.py` middleware to record presence on every tool call, and `get_narrator_context` surfacing of SOFY status.
- **yebyen/mecris is 5 commits ahead** of kingdonb/mecris (4 from Nag Ladder PR + 1 from Phase 1).

## Verified This Session
- [x] **SQL migration**: `scripts/migrations/001_presence_table.sql` created — `presence` table with `presence_status_type` enum (5 values).
- [x] **Neon presence store**: `ghost/presence.py` extended with `StatusType`, `PresenceRecord`, `NeonPresenceStore`, `get_neon_store()`. File-based lock API fully unchanged.
- [x] **17/17 new tests pass**: `tests/test_presence_neon.py` — upsert, get, POUND_SAND, SOFY escalation, fallback.
- [x] **29/29 existing ghost tests pass**: `test_ghost_presence.py` and `test_archivist.py` unaffected.
- [x] **Plan issue closed**: yebyen/mecris#69 closed as complete.

## Pending Verification (Next Session)

### Phase 2 — mcp_server.py middleware (kingdonb/mecris#164)
- Add middleware to `mcp_server.py` that calls `NeonPresenceStore.upsert(user_id, StatusType.ACTIVE_HUMAN)` on every tool invocation (when NEON_DB_URL is set).
- Expose `get_narrator_context` field surfacing current `status_type` — especially SOFY, so the narrator can warn the human when SHITS_ON_FIRE_YO is active.
- Test: mock `NeonPresenceStore` in `mcp_server` tests to verify middleware fires.
- Can only be E2E-validated in a live environment (Neon DB, running MCP server).

### Run SQL Migration on Live Neon DB
- `scripts/migrations/001_presence_table.sql` needs to be applied to the live Neon DB before the middleware can write presence records.
- Command: `psql $NEON_DB_URL -f scripts/migrations/001_presence_table.sql`

### PR Merge — Human Action Required
- kingdonb/mecris#165 needs review + merge by kingdonb.
- After merge, yebyen/mecris should sync (pull from kingdonb/mecris main).

### Ghost Archivist Live Validation (carry-forward)
- The archivist job fires every 15 minutes when `MecrisScheduler` is the leader.
- Can only be validated in a live environment (Neon DB, running MCP server).
- When next doing a live session, confirm `logs/ghost_archivist.log` accumulates PULSE entries.

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted. Use targeted `include_pattern` or `dir_path`.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **Nag Ladder tier semantics**:
    - Tier 1: WhatsApp Template (Gentle)
    - Tier 2: WhatsApp Freeform (Escalated, 6h idle) — coaching copy fully contextual for all types
    - Tier 3: WhatsApp Freeform High Urgency (Critical, runway < 2.0 hours — strictly less than)
- **Global Rate Limit**: 2 messages per hour across ALL channels.
- **ghost/ package**: Top-level package; import as `from ghost.presence import ...` or `from ghost.archivist import run` with `PYTHONPATH=.`.
- **Test command**: `PYTHONPATH=. .venv/bin/pytest` (create venv with `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest-cov pytest-asyncio`).
- **`uv` not available in CI**: Use `python3 -m venv .venv && .venv/bin/pip install` instead.
- **Scheduler election tests**: `tests/test_scheduler_election.py` requires psycopg2 — these fail in the bare CI environment. Pre-existing condition, not a regression.
- **GITHUB_TOKEN scope**: Fine-grained PAT for yebyen/mecris only. Cannot comment on kingdonb/mecris issues. **Use GITHUB_CLASSIC_PAT** for cross-repo operations (comment, PR creation — confirmed working session 15).
- **Presence table**: Schema in `scripts/migrations/001_presence_table.sql`. Must be applied to live Neon DB before Phase 2 middleware can write records. `NeonPresenceStore` gracefully returns None when NEON_DB_URL is unset.
