# Next Session: Health check complete — awaiting human-driven PRs (beta.2 dev cycle)

## Current Status (2026-04-19, post-health-report, plan yebyen/mecris#222)
- **yebyen/mecris is 1 commit ahead of kingdonb/mecris**: HEAD is `b8eb98e` (prior health commit, not merged upstream). No divergence.
- **Beta.2 dev cycle open**: Suite version bumped to `v0.0.1-beta.2` — next development iteration begins.
- **SLSA Build Level 1 achieved**: `7d3d981` adds cryptographically signed provenance for APK and WASM artifacts.
- **No open PRs on kingdonb/mecris**: Nothing to test. Wait for human-driven PRs.
- **One open issue on yebyen**: yebyen/mecris#142 (Rust CI fix) needs `workflow` PAT scope — must be applied by kingdonb. Out of bot scope.

## Verified This Session (2026-04-19, plan yebyen/mecris#222)
- [x] **Repos in sync**: yebyen HEAD `b8eb98e` is 1 ahead of kingdonb `34d8582` — health commits only, no divergence.
- [x] **No open PRs on kingdonb/mecris**: Confirmed — steady-state hold.
- [x] **No needs-test/pr-review/bug issues**: Confirmed — nothing actionable for bot.
- [x] **Health report opened**: yebyen/mecris#223 documents beta.2 dev cycle steady state.
- [x] **NEXT_SESSION.md updated**: Carried forward all pending items with 👤/🤖 scope markers.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Run migrate_v6 on production Neon**: `NEON_DB_URL=<prod> python scripts/migrate_v6_add_phone_verified.py` — needs human with Fermyon/Neon access.
- [ ] **Configure `cloud_provider` Spin variable**: Set `cloud_provider = "fermyon"` (or appropriate) in Fermyon Cloud runtime-config. New variable added in `mecris-go-spin/sync-service/spin.toml`.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. (Needs human with Fermyon access.)
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure — out of bot scope.
- [ ] **kingdonb/mecris#180 Part 1 (Android)**: Health Connect double-counting — Android-side fix. Out of bot scope.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Confirm Python test baseline via pr-test**: Estimated ~464 passed (unchanged). Verify on next PR test run when a PR is available.

## New Features Landed in beta.2 dev cycle (since beta.1 baseline `90a569e`)

- **feat(security): achieve SLSA Build Level 1** (`7d3d981`): Add `actions/attest-build-provenance` to Release workflow; generate signed provenance for APK and WASM; ROADMAP.md Alpha Hardening SLSA goals marked complete.
- **chore(config): remove --http flag from gemini MCP settings** (`b1d722e`): Beta testing config adjustment for Gemini MCP server.
- **chore(release): bump version to 0.0.1-beta.2** (`34d8582`): All 15+ ecosystem locations updated; dev cycle baseline set.

## Version Baseline (v0.0.1-beta.2 dev cycle)
- **Android**: 1.1.6-beta.2 (dev cycle bump)
- **Spin sync-service**: 0.3.1-beta.2
- **Python MCP**: 0.5.1-beta.2
- **Suite**: 0.0.1-beta.2
- **Web app**: Included in suite beta.2 bump

## Infrastructure Notes (carried forward)
- **phone_verified column**: `ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE` — in schema.sql AND migrate_v6. Apply migrate_v6 to production Neon.
- **phone_verifications table**: Created in schema.sql and migrate_v6. `UNIQUE(user_id)` — one pending verification per user.
- **scheduler_election now multi-user**: `user_id VARCHAR(255) FK`, `UNIQUE(user_id, role)` — old single-column `UNIQUE(role)` dropped in migrate_v6.
- **vacation_mode_until**: Added to schema.sql and migrate_v6. `NULL` = Boris & Fiona mode; `TIMESTAMP` = Generic Physical mode.
- **E2E skip guard**: `tests/test_phone_verification_e2e.py` skipped unless `RUN_E2E_TESTS=1`.
- **android_client_is_active**: `android_client_is_active(heartbeat_age_minutes: Option<u64>) -> bool` — returns `true` if Android heartbeated within 240 minutes (4 hours).
- **Ghost Nag guard query**: `SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60 AS minutes_since FROM scheduler_election WHERE user_id = $1 AND role = 'android_client' ORDER BY heartbeat DESC LIMIT 1`
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **greekNagMessage signature**: `greekNagMessage(arabicCleared: Boolean, isArabicHour: Boolean = true)` — default `true` preserves backwards compat.
- **DelayedNagWorker time guards**: Arabic fires 08:00–20:00; Walk fires 08:00+ (with weather/dark checks); GREEK fires 17:00–22:30, with Arabic-cleared override after 20:00.
- **Majesty Cake**: When `walkingSessionsCount > 0` or `totalDistanceMeters > 0.0` but `totalSteps < 2000`, fallback nag uses "MAJESTY CAKE 🍰" framing.
- **cloud_provider Spin variable**: New — `required = false, default = "unknown_cloud"`. Set `cloud_provider = "fermyon"` in Fermyon Cloud runtime-config.
- **Arabic 16pts/card heuristic**: Correct divisor is 16 (not 12). Used in both `lib.rs` and `scripts/clozemaster_scraper.py`.
- **Moussaka Exception**: `prefKey == "last_greek_nag_timestamp"` → 1.5h cooldown (5,400,000ms). All other nags: 4h (14,400,000ms).
- **global_last_nag_timestamp**: SharedPrefs key tracking last nag of any type. Both per-goal AND global cooldowns enforced.
- **Akamai Functions**: `/internal/failover-sync` and `/internal/trigger-reminders` guarded by `internal_api_key` (backwards compat: no key = allow all).
- **Spin Cron trigger**: DISABLED in `spin.toml` — do not re-enable.
- **MECRIS_MODE=standalone** bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope, no `read:org`.
- **Fine-grained PAT**: `GITHUB_TOKEN` scoped to yebyen/mecris only. Cannot create PRs on kingdonb/mecris — use `GITHUB_CLASSIC_PAT`.
- **Python venv not present in bot runner**: Validate Python tests via pr-test workflow only.
- **Python test count baseline**: ~464 passed (6 skipped), 0 failing. Rust: 108 passed. Android: 27 tests (1 pre-existing failure).
- **Rust satellite crates**: 99+ tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **bump_version.py now targets 15+ locations**: Covers Android, Spin, Python MCP, Web, and suite-level files.
- **SLSA Build Level 1**: `actions/attest-build-provenance` added to Release workflow. Signed provenance generated for APK + WASM artifacts.
