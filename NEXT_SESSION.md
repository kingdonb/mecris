# Next Session: kingdonb/mecris#165 awaiting review + merge — OIDC analysis complete

## Current Status (Friday, April 3, 2026 — session 23)
- **kingdonb/mecris#165** (PR) is open and awaiting review from kingdonb. NOT yet merged.
- **yebyen/mecris is 18 commits ahead** of kingdonb/mecris main — all work captured by PR #165 plus sessions 22–23 fixes.
- **Session 23** delivered: Full root cause analysis for OIDC submarine mode failures (kingdonb/mecris#162). Technical report posted to kingdonb/mecris#162. `docs/AUTH_CONFIGURATION.md` updated with 4-bug analysis and fix proposals. Commit `e9cc1c0`. Plan issue yebyen/mecris#81 closed.

## Verified This Session
- [x] `PocketIdAuth.kt:67` — missing `offline_access` scope identified as primary cause of Refresh Token loss
- [x] `PocketIdAuth.kt:109–112` — network errors treated as permanent auth failures (no distinction from `invalid_grant`)
- [x] `MainActivity.kt:1063–1074` — `AuthState.Error` shows "Sign In" button, which abandons valid Refresh Token on tap
- [x] No proactive token refresh in `WalkHeuristicsWorker` — only reactive on API calls
- [x] Technical report posted to kingdonb/mecris#162 (comment #4185361982)
- [x] `docs/AUTH_CONFIGURATION.md` — new "Root Cause Analysis" section added with code-level references and fix proposals

## Pending Verification (Next Session)

### PR Merge — Human Action Required
- kingdonb/mecris#165 needs review + merge by kingdonb.
- Once merged: yebyen/mecris should sync from upstream (`git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD`).
- Session 22 fix (score-delta, `d7945e3`) is NOT in PR #165 — after merge, open a new PR for it targeting kingdonb/mecris#130.

### OIDC Fix Implementation — Next Engineering Session
- kingdonb/mecris#162 analysis is DONE (report posted). Implementation is next:
  1. Add `"offline_access"` to scopes in `PocketIdAuth.kt:67`
  2. Distinguish transient vs. permanent auth failures in `getValidAccessToken` (`PocketIdAuth.kt:109–112`)
  3. Guard "Sign In" button behind `isPermanent` check in `SystemHealthScreen` (`MainActivity.kt:1063–1074`)
  4. Add proactive `getValidAccessToken()` call in `WalkHeuristicsWorker`
- Requires Android build to validate — can draft code in fork and dispatch pr-test.

### Other Open Work (after #165 merge)
- kingdonb/mecris#130 — Upstream activity tracking (score-delta fix in session 22 partially addresses; new PR needed)
- kingdonb/mecris#129 — Greek review backlog booster
- kingdonb/mecris#127 — Investigate "Cloud: Failover" status in Spin App

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
- **GITHUB_TOKEN scope**: Fine-grained PAT for yebyen/mecris only. **Use GITHUB_CLASSIC_PAT** for cross-repo operations (PR update, comment, PR creation, posting to kingdonb/mecris issues).
- **Presence table**: Schema in `scripts/migrations/001_presence_table.sql`. Must be applied to live Neon DB before Phase 2 middleware can write records. `get_neon_store()` gracefully returns None when NEON_DB_URL is unset.
- **Pre-existing test failures**: `tests/test_sms_mock.py` (3 failures + 1 subtest) and coaching/mcp-server/reminder-integration tests (fail in bare CI due to missing SQLAlchemy — not regressions).
- **PR #165 state**: Title and body fully updated through session 21. Awaiting kingdonb review only. Closes #139, #164, #97, #124.
- **HealthChecker service**: `services/health_checker.py` — `get_system_health(user_id)` returns `{processes: [...], overall_status: healthy|degraded}`. Stale threshold: 90 seconds.
- **Beeminder requestid**: `scripts/clozemaster_scraper.py` now passes `requestid = f"{goal_slug}-{today_eastern.strftime('%Y-%m-%d')}"` to `add_datapoint`. No prefetch call needed. Format documented in `tests/test_clozemaster_idempotency.py`.
- **Score-delta backup detection**: `services/language_sync_service.py` `_update_neon_db()` now uses score delta to set `daily_completions` when both `cards_today` and `points_today` are zero. Only fires when `last_points > 0` and `diff > daily_completions`. Commit `d7945e3` — NOT in PR #165.
- **OIDC submarine mode**: 4 bugs documented in `docs/AUTH_CONFIGURATION.md`. Technical report at kingdonb/mecris#162. Fix implementation is the next Android engineering task.
