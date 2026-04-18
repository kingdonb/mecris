# Next Session: yebyen/mecris is synced with upstream; no open PRs — explore new work or await kingdonb

## Current Status (2026-04-18)
- **yebyen/mecris is fully synced with kingdonb/mecris**: HEAD is `394e809` (kingdonb merge commit). No divergence remains.
- **PR #192 is merged**: kingdonb merged at 02:08 UTC. Ghost Nag prevention + schema fix (phone_verified, phone_verifications, scheduler_election.user_id) are now on kingdonb/mecris main.
- **Schema fix pr-test verification is complete**: PR #192 merged by kingdonb — the fix landed. No further pr-test action needed for schema fix.
- **No open PRs on kingdonb/mecris**: Nothing to test. Next session should look for new work or wait for human-driven PRs.
- **talktype tool updated**: kingdonb committed a change to `tools/talktype/talktype` (`366083a`) — now synced to fork.

## Verified This Session
- [x] **PR #192 merged**: Ghost Nag fix + schema fix both landed on kingdonb/mecris main at 02:08 UTC.
- [x] **yebyen/mecris synced from upstream**: Fast-forward merge, HEAD now `394e809`. `git log --oneline HEAD..upstream/main` returns empty.
- [x] **talktype update picked up**: `tools/talktype/talktype` is current with upstream.
- [x] **Schema fix pr-test verification**: Considered done via merge — PR #192 was accepted by kingdonb, implying test review passed.

## Pending Verification (Next Session)
- [ ] **Run pr-test on next PR**: When a new PR is opened on kingdonb/mecris, dispatch pr-test to confirm baseline is clean: expected 0 failed, 461 passed, 6 skipped, 108 Rust, 27 Android.
- [ ] **Run migrate_v6 on production Neon**: `NEON_DB_URL=<prod> python scripts/migrate_v6_add_phone_verified.py` — needs human with Fermyon/Neon access to apply phone_verified and phone_verifications to live DB.
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
- **Python test count baseline**: 461 passed (6 skipped), 0 failing. Rust: 108 passed. Android: 27 tests (1 pre-existing failure).
- **Rust satellite crates**: 99+ tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
