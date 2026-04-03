# Next Session: kingdonb/mecris#165 awaiting review + OIDC fixes implemented — update PR body

## Current Status (Friday, April 3, 2026 — session 24)
- **kingdonb/mecris#165** (PR) is open and awaiting review from kingdonb. NOT yet merged.
- **yebyen/mecris is 20 commits ahead** of kingdonb/mecris main — PR #165 now includes sessions 13–24 (Nag Ladder, Ghost Presence, Idempotent Beeminder, score-delta fix, OIDC analysis + implementation).
- **Session 24** delivered: All 4 OIDC submarine mode fixes implemented in `PocketIdAuth.kt`, `MainActivity.kt`, `WalkHeuristicsWorker.kt`. `docs/AUTH_CONFIGURATION.md` updated to reflect implementation status. Commit `1151698`.
- **pr-test run 23966570693** completed with ✅ success (Android unit tests + pytest).
- **PR #165 body is outdated** — still describes only sessions 13-20. Needs section added for sessions 22–24 (score-delta, OIDC analysis, OIDC implementation).

## Verified This Session
- [x] `PocketIdAuth.kt:67` — `"offline_access"` scope added; Pocket-ID will now issue durable Refresh Token
- [x] `PocketIdAuth.kt:109–112` — transient network errors no longer set `AuthState.Error`; only `TYPE_OAUTH_TOKEN_ERROR` triggers permanent error state
- [x] `AuthState.Error` — `isPermanent: Boolean = true` field added
- [x] `MainActivity.kt:1063–1074` — Idle/Error branches split; Sign In button guarded behind `state.isPermanent`
- [x] `WalkHeuristicsWorker.kt` — proactive refresh comment updated; existing `getAccessTokenSuspend()` call at top of `doWork()` confirmed as the proactive refresh
- [x] `docs/AUTH_CONFIGURATION.md` — all 4 bugs marked ✅ Fixed
- [x] pr-test run 23966570693 — ✅ success (Android + Python)

## Pending Verification (Next Session)

### PR Merge — Human Action Required
- kingdonb/mecris#165 needs review + merge by kingdonb.
- PR body should be updated to add session 22–24 sections (score-delta, OIDC analysis, OIDC implementation) before or after merge.
- Once merged: yebyen/mecris should sync from upstream (`git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD`).

### Post-Merge PRs
- After #165 merges, all 20 commits land (sessions 13–24). No separate PRs needed for score-delta or OIDC — they're already in the PR.
- kingdonb/mecris#162 (OIDC) and kingdonb/mecris#130 (score-delta) can be closed once #165 merges.

### OIDC Fix — Live Validation
- The OIDC fixes are code-only; they require a live Android device + app build to validate end-to-end.
- Specifically: verify app retains Refresh Token after 1h Access Token expiry with auth server unreachable.
- Intermediate validation: Android unit tests already passing via pr-test.

### Other Open Work (after #165 merge)
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
- **PR #165 state**: Title and body describe sessions 13-20 only. Body needs sessions 22-24 sections. Awaiting kingdonb review. Closes #139, #164, #97, #124 (and now also partially addresses #162, #130).
- **HealthChecker service**: `services/health_checker.py` — `get_system_health(user_id)` returns `{processes: [...], overall_status: healthy|degraded}`. Stale threshold: 90 seconds.
- **Beeminder requestid**: `scripts/clozemaster_scraper.py` now passes `requestid = f"{goal_slug}-{today_eastern.strftime('%Y-%m-%d')}"` to `add_datapoint`. No prefetch call needed.
- **Score-delta backup detection**: `services/language_sync_service.py` `_update_neon_db()` uses score delta to set `daily_completions` when both `cards_today` and `points_today` are zero. Commit `d7945e3`.
- **OIDC submarine mode**: All 4 bugs fixed in commit `1151698`. `offline_access` scope added; transient errors distinguished from permanent; Sign In button guarded; proactive refresh confirmed in WalkHeuristicsWorker. Docs updated.
