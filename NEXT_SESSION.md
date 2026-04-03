# Next Session: kingdonb/mecris#165 awaiting review + merge — PR body complete through session 20

## Current Status (Friday, April 3, 2026 — session 21)
- **kingdonb/mecris#165** (PR) is open and fully describes all work: Nag Ladder (sessions 13–14), Ghost Presence (sessions 16–17), System Health (session 19), and Idempotent Beeminder (session 20). Title updated to "sessions 13-20".
- **yebyen/mecris is 14 commits ahead** of kingdonb/mecris main — all work captured by PR #165.
- **Session 21** delivered: PR #165 title + body updated to include session 20 (idempotent Beeminder `requestid`) and `Closes kingdonb/mecris#124`. Plan issue yebyen/mecris#77 closed.

## Verified This Session
- [x] PR #165 title updated: "feat: Complete Nag Ladder + Ghost Presence + Idempotent Beeminder — sessions 13-20"
- [x] PR #165 body: session 20 section added describing `requestid`-based idempotency in `scripts/clozemaster_scraper.py` and `tests/test_clozemaster_idempotency.py`.
- [x] PR #165 closing keywords: `Closes kingdonb/mecris#124` appended — all four issues now listed (#139, #164, #97, #124).
- [x] PR test plan updated: 5/5 `test_clozemaster_idempotency.py` + 217 passing total.

## Pending Verification (Next Session)

### PR Merge — Human Action Required
- kingdonb/mecris#165 needs review + merge by kingdonb.
- Once merged: yebyen/mecris should sync from upstream (`git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD`).

### Open New Work
- After merge, consider new issue to tackle from the open list:
  - kingdonb/mecris#162 — OIDC token refresh / Submarine Mode analysis
  - kingdonb/mecris#130 — Upstream activity tracking from Clozemaster points
  - kingdonb/mecris#129 — Greek review backlog booster

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
- **PR #165 state**: Title and body fully updated through session 21. Awaiting kingdonb review only. Closes #139, #164, #97, #124.
- **HealthChecker service**: `services/health_checker.py` — `get_system_health(user_id)` returns `{processes: [...], overall_status: healthy|degraded}`. Stale threshold: 90 seconds.
- **Beeminder requestid**: `scripts/clozemaster_scraper.py` now passes `requestid = f"{goal_slug}-{today_eastern.strftime('%Y-%m-%d')}"` to `add_datapoint`. No prefetch call needed. Format documented in `tests/test_clozemaster_idempotency.py`.
