# Next Session: verify schema fix (pr-test should show 0 failed after push) and await PR #192 merge

## Current Status (2026-04-18)
- **PR #192 open**: kingdonb/mecris#192 — Ghost Nag prevention fix. Awaiting kingdonb review/merge. No bot action needed.
- **yebyen/mecris is 4 commits ahead of kingdonb/mecris**: commit `4391848` (schema fix) is the newest, not yet pushed to GitHub (push happens when mecris-bot.yml ends)
- **Schema fix committed** (`4391848`): adds `phone_verified`, `vacation_mode_until`, `phone_verifications` table, and `scheduler_election.user_id` to `schema.sql`; adds E2E skip guard to `test_phone_verification_e2e.py`; adds `migrate_v6_add_phone_verified.py`
- **pr-test NOT yet verified for schema fix**: the verification run (24592087704) used pre-push code from GitHub — still showed 1 failed. Next session must re-run pr-test after push to confirm 0 failed.
- **pr-test baselines confirmed this session**: Rust 108 ✅, Python 461 passed/1 failed (pre-existing), Android 27 tests (run 24591839834)

## Verified This Session
- [x] **Rust test baseline is 108**: run 24591839834 confirmed 108 Rust tests post-push (was 107 pre-push)
- [x] **Android test count is 27**: run 24591839834 — 27 tests completed, 1 pre-existing failure (`PocketIdAuthTest`)
- [x] **internal_api_key already implemented**: Rust code at `lib.rs:196-211` already checks `X-Internal-Api-Key` header; 4 passing tests (lines 2735-2757). kingdonb/mecris#185 is code-complete, remaining work is Fermyon Cloud deployment.
- [x] **Schema gaps identified and fixed**: `phone_verified` BOOLEAN, `vacation_mode_until` TIMESTAMPTZ (users table), `phone_verifications` table, `scheduler_election.user_id` FK + `UNIQUE(user_id, role)` constraint — all added to `schema.sql` + migration script.

## Pending Verification (Next Session)
- [ ] **FIRST: Run pr-test on PR #192** to confirm schema fix works after push: expected 0 failed, 461 passed, 6 skipped (was 1 failed, 461 passed, 5 skipped). See yebyen/mecris#212.
- [ ] **PR #192 review/merge**: kingdonb needs to review and merge kingdonb/mecris#192 (Ghost Nag fix). Bot should check if still open.
- [ ] **Run migrate_v6 on production Neon**: `NEON_DB_URL=<prod> python scripts/migrate_v6_add_phone_verified.py` — needs human with Fermyon/Neon access to apply `phone_verified` and `phone_verifications` to live DB.
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure — `java.lang.ExceptionInInitializerError` at `PocketIdAuthTest.kt:35`. Out of bot scope (Android-side fix).
- [ ] **kingdonb/mecris#191 full resolution**: PR #192 implements Option A (Cloud stands down). Option B (Android logs to message_log) still open — not bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. (Needs human with Fermyon access.)
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.
- [ ] **kingdonb/mecris#180 Part 1 (Android)**: Health Connect double-counting — Android-side source filtering fix. Out of bot scope.

## Infrastructure Notes
- **phone_verified column**: `ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE` — in schema.sql AND migrate_v6. Apply migrate_v6 to production Neon before the E2E test can run live.
- **phone_verifications table**: Created in schema.sql and migrate_v6. `UNIQUE(user_id)` — one pending verification per user.
- **scheduler_election now multi-user**: `user_id VARCHAR(255) FK`, `UNIQUE(user_id, role)` — old single-column `UNIQUE(role)` dropped in migrate_v6. Ghost Nag query at `lib.rs:1339` depends on this.
- **vacation_mode_until**: Added to schema.sql and migrate_v6. `NULL` = Boris & Fiona mode; `TIMESTAMP` = Generic Physical mode (from PRD kingdonb/mecris#188).
- **E2E skip guard**: `tests/test_phone_verification_e2e.py` now has `pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E_TESTS'), ...)` — test skipped in CI unless `RUN_E2E_TESTS=1` is set.
- **android_client_is_active**: `android_client_is_active(heartbeat_age_minutes: Option<u64>) -> bool` — returns `true` if Android heartbeated within 240 minutes (4 hours). Integrated into `handle_trigger_reminders_post`.
- **Ghost Nag guard query**: `SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60 AS minutes_since FROM scheduler_election WHERE user_id = $1 AND role = 'android_client' ORDER BY heartbeat DESC LIMIT 1`
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this. Regression test: `test_aggregate_step_count_ordering_contract`.
- **greekNagMessage signature**: `greekNagMessage(arabicCleared: Boolean, isArabicHour: Boolean = true)` — default `true` preserves backwards compat.
- **DelayedNagWorker time guards**: Arabic fires 08:00–20:00; Walk fires 08:00+ (with weather/dark checks); GREEK fires 17:00–22:30, with Arabic-cleared override after 20:00.
- **Majesty Cake**: When `walkingSessionsCount > 0` or `totalDistanceMeters > 0.0` but `totalSteps < 2000`, Android nags use "MAJESTY CAKE 🍰" framing.
- **Akamai Functions**: `/internal/failover-sync` and `/internal/trigger-reminders` guarded by `internal_api_key` Spin variable (backwards compat: no key = allow all).
- **Spin Cron trigger**: DISABLED in `spin.toml` — do not re-enable.
- **MECRIS_MODE=standalone** bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope, no `read:org`.
- **Fine-grained PAT**: `GITHUB_TOKEN` scoped to yebyen/mecris only. Cannot create PRs on kingdonb/mecris — use `GITHUB_CLASSIC_PAT`.
- **Python venv not present in bot runner**: Validate Python tests via pr-test workflow only.
- **Python test count baseline**: 461 passed (5 skipped) — 1 failing (pre-existing, now fixed in schema; will be 0 failing / 6 skipped after push+pr-test). Rust: 108 passed. Android: 27 tests (1 pre-existing failure).
- **Rust satellite crates**: 99+ tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false`.
- **Phone verification**: E2E test skip guard added in `4391848`; schema fix in same commit. Live E2E still blocked (needs Fermyon Neon + Twilio vars).
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
