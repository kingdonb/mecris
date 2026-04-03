# Next Session: kingdonb/mecris#165 awaiting review + merge — open new PR for idempotent Beeminder pushes

## Current Status (Friday, April 3, 2026 — session 20)
- **kingdonb/mecris#165** (PR) is open and fully describes Nag Ladder (sessions 13–14), Ghost Presence (sessions 16–17), and System Health (session 19). Body updated this session to include `get_system_health` description and `Closes kingdonb/mecris#97`.
- **yebyen/mecris is 13 commits ahead** of kingdonb/mecris main — all prior work captured by PR #165 plus session 20 commit.
- **Session 20** delivered: `requestid`-based idempotent Beeminder datapoint pushes (closes kingdonb/mecris#124). Commit `e2a5682`.

## Verified This Session
- [x] PR #165 body updated via REST API (GITHUB_CLASSIC_PAT) — now includes session 19 (`get_system_health`) description and `Closes kingdonb/mecris#97`.
- [x] `scripts/clozemaster_scraper.py`: removed check-then-push pattern; `add_datapoint` now receives `requestid = f"{goal_slug}-{today_eastern.strftime('%Y-%m-%d')}"` on every push.
- [x] `tests/test_clozemaster_idempotency.py`: 5 tests rewritten to assert `requestid` format, absence of `get_goal_datapoints` call, dry-run skip, and unknown-goal skip. 5/5 pass.
- [x] Full test suite: 217 passing, 0 new regressions (pre-existing: test_sms_mock 3+1, SQLAlchemy CI failures).

## Pending Verification (Next Session)

### PR Merge — Human Action Required
- kingdonb/mecris#165 needs review + merge by kingdonb.
- Once merged: yebyen/mecris should sync from upstream (`git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD`).

### Open New PR for Session 20 Work
- `scripts/clozemaster_scraper.py` + `tests/test_clozemaster_idempotency.py` (commit `e2a5682`) are on yebyen/mecris main but NOT in any PR to kingdonb/mecris.
- Next session: decide whether to bundle into #165 (update) or open a new PR post-merge referencing `Closes kingdonb/mecris#124`.

### Run SQL Migration on Live Neon DB
- `scripts/migrations/001_presence_table.sql` needs to be applied before the Ghost Presence middleware can write records.
- Command: `psql $NEON_DB_URL -f scripts/migrations/001_presence_table.sql`

### get_system_health Live Validation
- `get_system_health` returns `{"error": "NEON_DB_URL not configured"}` if Neon unavailable.
- Live validation: call `get_system_health` from a running MCP session and confirm `scheduler_election` rows are returned.

### Ghost Archivist Live Validation (carry-forward)
- The archivist job fires every 15 minutes when `MecrisScheduler` is the leader.
- Validate in a live environment: `logs/ghost_archivist.log` should accumulate PULSE entries.

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
- **Scheduler election tests**: `tests/test_scheduler_election.py` requires psycopg2 + SQLAlchemy — these fail in bare CI. Pre-existing condition.
- **GITHUB_TOKEN scope**: Fine-grained PAT for yebyen/mecris only. **Use GITHUB_CLASSIC_PAT** for cross-repo operations (PR update, comment, PR creation).
- **Presence table**: Schema in `scripts/migrations/001_presence_table.sql`. Must be applied to live Neon DB before Phase 2 middleware can write records. `get_neon_store()` gracefully returns None when NEON_DB_URL is unset.
- **Pre-existing test failures**: `tests/test_sms_mock.py` (3 failures + 1 subtest) and coaching/mcp-server/reminder-integration tests (fail in bare CI due to missing SQLAlchemy — not regressions).
- **PR #165 state**: title and body fully updated sessions 18+20. Awaiting kingdonb review only.
- **HealthChecker service**: `services/health_checker.py` — `get_system_health(user_id)` returns `{processes: [...], overall_status: healthy|degraded}`. Stale threshold: 90 seconds.
- **Beeminder requestid**: `scripts/clozemaster_scraper.py` now passes `requestid = f"{goal_slug}-{today_eastern.strftime('%Y-%m-%d')}"` to `add_datapoint`. No prefetch call needed. Format documented in `tests/test_clozemaster_idempotency.py`.
