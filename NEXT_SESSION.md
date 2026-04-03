# Next Session: kingdonb/mecris#165 awaiting review + merge — SQL migration + live validation pending

## Current Status (Friday, April 3, 2026 — session 19)
- **kingdonb/mecris#165** (PR) is open, up-to-date with yebyen/mecris HEAD (`52136cb`), and fully describes all work: Nag Ladder (sessions 13–14) + Ghost Presence Phases 1+2 (sessions 16–17). Both `Closes kingdonb/mecris#139` and `Closes kingdonb/mecris#164` are in the body.
- **session 19** delivered: `get_system_health` MCP tool (kingdonb/mecris#97) + pre-existing `test_language_sync_service_coordination` test failure fixed. Commit `52136cb`.
- **yebyen/mecris is 11 commits ahead** of kingdonb/mecris main — all prior work captured by PR #165; session 19 commit is on top.

## Verified This Session
- [x] `services/health_checker.py`: `HealthChecker.get_system_health()` reads `scheduler_election` table, returns `processes[]` (role, is_active, last_heartbeat ISO) + `overall_status` (healthy/degraded).
- [x] `mcp_server.py`: `get_system_health` tool delegates to `HealthChecker`, appends `leader_process_id` and `is_leader` from live `MecrisScheduler`.
- [x] `tests/test_system_health.py`: 6 new tests pass (all_active, stale, no_neon_url, db_error, heartbeat_serialized, mixed_active).
- [x] `tests/test_language_sync_service.py`: pre-existing failure fixed — `mock_beeminder.user_id = None` + replaced fragile `call_count == 4` with content-based INSERT assertions. 1 pre-existing failure → 0.
- [x] Full test suite: 214 passing, 0 new regressions (pre-existing: test_sms_mock 3+1, scheduler/coaching/mcp-server tests fail in bare CI due to missing SQLAlchemy/apscheduler).

## Pending Verification (Next Session)

### PR Merge — Human Action Required
- kingdonb/mecris#165 needs review + merge by kingdonb.
- Once merged: yebyen/mecris should sync from upstream (`git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD`).

### Session 19 Additions — Not Yet in PR #165
- `services/health_checker.py`, `mcp_server.py` (get_system_health), `tests/test_system_health.py`, updated `tests/test_language_sync_service.py` are committed to yebyen/mecris `main` (commit `52136cb`) but **not** in any open PR to kingdonb/mecris.
- Next session should decide: fold into PR #165 (update branch) or open a new PR after #165 merges.

### Run SQL Migration on Live Neon DB
- `scripts/migrations/001_presence_table.sql` needs to be applied to the live Neon DB before the middleware can write presence records.
- Command: `psql $NEON_DB_URL -f scripts/migrations/001_presence_table.sql`
- Without this, `get_neon_store()` returns None in production (graceful no-op).

### get_system_health Live Validation
- `get_system_health` returns `{"error": "NEON_DB_URL not configured", "processes": []}` if Neon is unavailable.
- Live validation: call `get_system_health` from a running MCP session and verify `scheduler_election` rows are returned with accurate `is_active` flags.

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
- **Test command**: `PYTHONPATH=. .venv/bin/pytest` (create venv with `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest-cov pytest-asyncio mcp apscheduler`).
- **`uv` not available in CI**: Use `python3 -m venv .venv && .venv/bin/pip install` instead.
- **Scheduler election tests**: `tests/test_scheduler_election.py` requires psycopg2 + SQLAlchemy — these fail in the bare CI environment. Pre-existing condition, not a regression.
- **GITHUB_TOKEN scope**: Fine-grained PAT for yebyen/mecris only. Cannot comment on kingdonb/mecris issues. **Use GITHUB_CLASSIC_PAT** for cross-repo operations (comment, PR update, PR creation — confirmed working sessions 15 + 18).
- **Presence table**: Schema in `scripts/migrations/001_presence_table.sql`. Must be applied to live Neon DB before Phase 2 middleware can write records. `get_neon_store()` gracefully returns None when NEON_DB_URL is unset or psycopg2 unavailable.
- **Pre-existing test failures**: `tests/test_sms_mock.py` (3 failures + 1 subtest) and coaching/mcp-server/reminder-integration tests (fail in bare CI due to missing SQLAlchemy — not regressions).
- **PR #165 state**: title and body fully updated session 18. Awaiting kingdonb review only.
- **HealthChecker service**: `services/health_checker.py` — `get_system_health(user_id)` returns `{processes: [...], overall_status: healthy|degraded}`. Stale threshold: 90 seconds. Tests: `tests/test_system_health.py`.
