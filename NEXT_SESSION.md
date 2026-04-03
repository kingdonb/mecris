# Next Session: Ghost Presence Phase 2 complete — open upstream PR for kingdonb/mecris#164

## Current Status (Friday, April 3, 2026 — session 17)
- **Ghost Presence Phase 2 complete** (commit `16c91ac`): `mcp_server.py` now calls `_record_presence(user_id)` in `get_narrator_context`, upserts `ACTIVE_HUMAN` on every invocation (no-op when `NEON_DB_URL` unset). `get_narrator_context` returns `presence_status` field (SOFY visible to narrator). 4 new unit tests pass in `tests/test_mcp_server.py`.
- **kingdonb/mecris#164** (Ghost Presence Neon Evolution): Phases 1 and 2 both done in yebyen fork. Phase 3 remaining: open upstream PR to kingdonb/mecris.
- **kingdonb/mecris#165** (Nag Ladder PR) still open — awaiting human review + merge.
- **yebyen/mecris is 6 commits ahead** of kingdonb/mecris (4 Nag Ladder + 1 Phase 1 + 1 Phase 2).

## Verified This Session
- [x] **`_record_presence()` helper**: calls `NeonPresenceStore.upsert(user_id, ACTIVE_HUMAN, "mcp_server")` when Neon available; no-op when `get_neon_store()` returns None; swallows DB errors.
- [x] **`_get_presence_status()` helper**: calls `NeonPresenceStore.get(user_id)`, returns `status_type.value` string or None.
- [x] **`get_narrator_context` wired**: calls `_record_presence` before building response; returns `presence_status` key.
- [x] **4/4 new tests pass**: `tests/test_mcp_server.py` — upsert with ACTIVE_HUMAN, no-op when None, exception swallowed, presence_status in narrator dict.
- [x] **0 regressions**: 218 passing tests unchanged (5 pre-existing failures in test_sms_mock.py + test_language_sync_service.py confirmed pre-existing).
- [x] **Plan issue closed**: yebyen/mecris#70 closed as complete.

## Pending Verification (Next Session)

### Open Upstream PR for Ghost Presence (kingdonb/mecris#164)
- yebyen/mecris is 6 commits ahead. Commits `2e6e11b` (Phase 1) + `16c91ac` (Phase 2) represent the Ghost Presence work.
- Need to open a PR to kingdonb/mecris for the full Ghost Presence feature (Phases 1 + 2).
- Use `GITHUB_CLASSIC_PAT` for cross-repo PR creation (confirmed working session 15).
- PR body should reference kingdonb/mecris#164 and include Phase 1 + Phase 2 summary.

### Run SQL Migration on Live Neon DB
- `scripts/migrations/001_presence_table.sql` needs to be applied to the live Neon DB before the middleware can write presence records.
- Command: `psql $NEON_DB_URL -f scripts/migrations/001_presence_table.sql`
- Without this, `get_neon_store()` returns None in production (graceful no-op).

### PR Merge — Human Action Required
- kingdonb/mecris#165 (Nag Ladder) needs review + merge by kingdonb.
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
- **Presence table**: Schema in `scripts/migrations/001_presence_table.sql`. Must be applied to live Neon DB before Phase 2 middleware can write records. `get_neon_store()` gracefully returns None when NEON_DB_URL is unset or psycopg2 unavailable.
- **Pre-existing test failures**: `tests/test_sms_mock.py` (3 failures + 1 subtest) and `tests/test_language_sync_service.py::test_language_sync_service_coordination` — not regressions, confirmed present before session 17 changes.
