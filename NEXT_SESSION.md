# Next Session: kingdonb/mecris#165 awaiting review + merge — PR body complete through session 20

## Current Status (Friday, April 3, 2026 — session 22)
- **kingdonb/mecris#165** (PR) is open and fully describes all work: Nag Ladder (sessions 13–14), Ghost Presence (sessions 16–17), System Health (session 19), and Idempotent Beeminder (session 20). Title updated to "sessions 13-20".
- **yebyen/mecris is 16 commits ahead** of kingdonb/mecris main — all work captured by PR #165 plus session 22 fix.
- **Session 22** delivered: Fixed no-op score-delta backup detection in `services/language_sync_service.py`; added `test_score_delta_backup_detection_updates_daily_completions`; 218 passing total. Addresses kingdonb/mecris#130 (Upstream Activity Tracking). Plan issue yebyen/mecris#79 closed.

## Verified This Session
- [x] `_update_neon_db()` backup activity detection now updates `daily_completions` from score delta when `cards_today=0` and `points_today=0`
- [x] New test: `test_score_delta_backup_detection_updates_daily_completions` — delta=100 asserted when last_points=500→points=600 with no upstream "today" data
- [x] Full test suite: 218 passing, 0 regressions (15 pre-existing failures unchanged)

## Pending Verification (Next Session)

### PR Merge — Human Action Required
- kingdonb/mecris#165 needs review + merge by kingdonb.
- Once merged: yebyen/mecris should sync from upstream (`git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD`).
- Session 22 fix (score-delta) is NOT in PR #165 — after merge, open a new PR or add it to a follow-up.

### New PR for Session 22 Work
- After PR #165 merges, open a new PR for the score-delta fix (`d7945e3`) targeting kingdonb/mecris#130.

### Open New Work (after #165 merge)
- kingdonb/mecris#162 — OIDC token refresh / Submarine Mode analysis
- kingdonb/mecris#130 — Upstream activity tracking from Clozemaster points (partially addressed; score delta now works)
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
- **Score-delta backup detection**: `services/language_sync_service.py` `_update_neon_db()` now uses score delta to set `daily_completions` when both `cards_today` and `points_today` are zero. Only fires when `last_points > 0` and `diff > daily_completions`.
