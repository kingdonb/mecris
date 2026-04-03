# Next Session: kingdonb/mecris#165 awaiting review + merge — SQL migration + live validation pending

## Current Status (Friday, April 3, 2026 — session 18)
- **kingdonb/mecris#165** (PR) is open, up-to-date with yebyen/mecris HEAD (`9e84dfd`), and now fully describes all work: Nag Ladder (sessions 13–14) + Ghost Presence Phases 1+2 (sessions 16–17). Both `Closes kingdonb/mecris#139` and `Closes kingdonb/mecris#164` are in the body.
- **kingdonb/mecris#164** (Ghost Presence issue): will auto-close when #165 merges.
- **kingdonb/mecris#139** (Nag Ladder issue): will auto-close when #165 merges.
- **yebyen/mecris is 9 commits ahead** of kingdonb/mecris main — all captured by PR #165.

## Verified This Session
- [x] **PR #165 title updated**: now reads "feat: Complete Nag Ladder + Ghost Presence (Neon-backed coordination) — sessions 13-17"
- [x] **PR #165 body updated**: covers sessions 13–17 with Ghost Presence Phases 1+2 detail, state machine diagram, pending live-validation items, and full test plan.
- [x] **`Closes kingdonb/mecris#139`** present in PR body.
- [x] **`Closes kingdonb/mecris#164`** present in PR body — presence issue will close on merge.

## Pending Verification (Next Session)

### PR Merge — Human Action Required
- kingdonb/mecris#165 needs review + merge by kingdonb.
- Once merged: yebyen/mecris should sync from upstream (`git fetch upstream && git merge upstream/main`).

### Run SQL Migration on Live Neon DB
- `scripts/migrations/001_presence_table.sql` needs to be applied to the live Neon DB before the middleware can write presence records.
- Command: `psql $NEON_DB_URL -f scripts/migrations/001_presence_table.sql`
- Without this, `get_neon_store()` returns None in production (graceful no-op).

### Ghost Archivist Live Validation (carry-forward)
- The archivist job fires every 15 minutes when `MecrisScheduler` is the leader.
- Can only be validated in a live environment (Neon DB, running MCP server).
- When next doing a live session, confirm `logs/ghost_archivist.log` accumulates PULSE entries.

### Post-Merge Sync
- After kingdonb merges #165: run `git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD` in yebyen/mecris to bring the fork back to parity.

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
- **GITHUB_TOKEN scope**: Fine-grained PAT for yebyen/mecris only. Cannot comment on kingdonb/mecris issues. **Use GITHUB_CLASSIC_PAT** for cross-repo operations (comment, PR update, PR creation — confirmed working sessions 15 + 18).
- **Presence table**: Schema in `scripts/migrations/001_presence_table.sql`. Must be applied to live Neon DB before Phase 2 middleware can write records. `get_neon_store()` gracefully returns None when NEON_DB_URL is unset or psycopg2 unavailable.
- **Pre-existing test failures**: `tests/test_sms_mock.py` (3 failures + 1 subtest) and `tests/test_language_sync_service.py::test_language_sync_service_coordination` — not regressions, confirmed present before session 17 changes.
- **PR #165 state**: title and body fully updated session 18. Awaiting kingdonb review only.
