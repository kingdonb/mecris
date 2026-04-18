# Next Session: yebyen/mecris synced with upstream — 21 commits audited

## Current Status (2026-04-18, post-sync)
- **yebyen/mecris is fully synced with kingdonb/mecris**: HEAD is `65f24a0`. No divergence.
- **No open PRs on kingdonb/mecris**: Nothing to test. Wait for human-driven PRs.
- **One open issue on yebyen**: yebyen/mecris#142 (Rust CI fix) needs `workflow` PAT scope — must be applied by kingdonb. Out of bot scope.
- **Arabic Majesty Cake achieved**: 170/170 Arabic cards done as of 2026-04-18!

## Verified This Session (2026-04-18, plan yebyen/mecris#217)
- [x] **Upstream sync complete**: 21 commits merged from kingdonb/mecris (fast-forward, no conflicts)
- [x] **NEXT_SESSION.md updated**: New baseline `65f24a0`, infrastructure notes extracted
- [x] **Version baseline**: Android 1.1.6-alpha.6, Spin 0.3.1-alpha.6, Python MCP 0.5.1-alpha.6, Suite 0.0.1-alpha.6

## Pending Verification (Next Session)
- [ ] **Confirm Python test baseline via pr-test**: Estimated ~464 passed (unchanged — test mods were behavior fixes, not count changes). Verify on next PR test run.
- [ ] **Run migrate_v6 on production Neon**: `NEON_DB_URL=<prod> python scripts/migrate_v6_add_phone_verified.py` — needs human with Fermyon/Neon access.
- [ ] **Configure `cloud_provider` Spin variable**: Set `cloud_provider = "fermyon"` (or appropriate) in Fermyon Cloud runtime-config. New variable added in `mecris-go-spin/sync-service/spin.toml`.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. (Needs human with Fermyon access.)
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure — out of bot scope.
- [ ] **kingdonb/mecris#180 Part 1 (Android)**: Health Connect double-counting — Android-side fix. Out of bot scope.

## New Features Landed Since Last Sync (audit by yebyen/mecris#217)

### Post-merge upstream commits (3 new commits since yebyen/main was merged):
- **feat(neural-link)**: `/languages` endpoint now wraps response to match frontend expectations; filters inactive languages (no Beeminder goal) from web UI except Arabic; enriches stats with `absolute_target`, `target_flow_rate`, `goal_met`, `has_goal`; Majesty Cake visualizer has pulsing animation
- **fix(android)**: Sovereign Fallback nag now checks `global_last_nag_timestamp` cooldown; `PROGRESS: /` bug fixed by ensuring full data flow; ReviewPump shows Progress / Absolute Target; green orb color preference restored

### Pre-merge upstream commits (18 commits already in kingdonb before yebyen/main was merged):
- **Moussaka Exception**: Greek nag cooldown reduced to 1.5h (5,400,000ms) when `prefKey == "last_greek_nag_timestamp"`. Default cooldown remains 4h.
- **Global nag cooldown**: `global_last_nag_timestamp` SharedPrefs key — prevents 'machine gun' nagging. Both per-goal and global cooldowns must be satisfied.
- **Fermyon heartbeats re-enabled** in sync-service (`65cbd5b`)
- **`cloud_provider` Spin variable**: New in `spin.toml` with default `"unknown_cloud"`. Set in Fermyon Cloud runtime-config.
- **Arabic heuristic fixed**: 16 pts/card (was 12 effective). Prevents premature 'goal met' in sync-service AND Python scraper.
- **`get_modality_status()` in mcp_server.py**: Maps heartbeat age to healthy/degraded/offline per role: leader (<2min healthy), android_client (<20min), akamai_functions (<135min), fermyon_cloud (<5min reactive)
- **Neural-link UI**: Fermyon Cloud shows gray when stale; human-friendly pulse modality names; priority active worker pulse over reactive reachability
- **Manual cloud reconciliation**: Web UI feedback for manual sync
- **Test alignment**: `test_standalone_mode_no_id_returns_none` — standalone mode now returns `None` (was generating a local ID). `mcp_server` status tests patched for mock type errors.
- **Android version**: 1.1.6-alpha.6; Spin suite: 0.0.1-alpha.6; sync-service: 0.3.1-alpha.6
- **`scripts/clozemaster_scraper.py`**: Updated Arabic heuristic (16pts/card divisor); Neon persistence enabled

## Infrastructure Notes (carried forward + new)
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
