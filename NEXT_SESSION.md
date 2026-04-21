# Next Session: Human review and merge of kingdonb/mecris#198 (beta.2 PR — 8 commits)

## Current Status (2026-04-21, post-session #21, plan yebyen/mecris#245)
- **PR open**: kingdonb/mecris#198 — yebyen:main → kingdonb:main, 8 commits (7 feature + 1 compile fix). Ready for human review.
- **Test baseline correct**: Python 480 passed / 6 skipped — confirmed accurate (yebyen/mecris#245). Previous "expected 506" was based on an overstated baseline (464 vs ~437 actual).
- **yebyen/mecris#142 closed**: Rust CI fix was applied by kingdonb; issue closed in session #21.
- **Repos status**: yebyen is 9 commits ahead of kingdonb (8 feature/fix + 1 baseline correction commit). All 8 feature commits in PR #198.

## Verified This Session (2026-04-21, session #21, plan yebyen/mecris#245)
- [x] **Plan issue opened**: yebyen/mecris#245 — recorded before touching code.
- [x] **Python test count investigation**: 26-test gap explained (yebyen/mecris#245#comment). Overstated baseline (464 vs ~437 actual) + obsidian 19 (not 20) + headless 24 (not 22). No tests broken.
- [x] **yebyen/mecris#142 closed**: Rust CI working-directory fix confirmed applied; stale issue closed.
- [x] **NEXT_SESSION.md baseline corrected**: "expected 506" warning removed; committed `b3b1bfc`.
- [x] **Plan issue closed**: yebyen/mecris#245 closed with completion comment.

## Previously Verified (2026-04-21, session #20, plan yebyen/mecris#244)
- [x] **Plan issue opened**: yebyen/mecris#244 — recorded before touching any code.
- [x] **PR opened**: kingdonb/mecris#198 — yebyen:main → kingdonb:main, 7 feature commits.
- [x] **Android compile error found and fixed**: `remainingToday` typed as `Number` (common supertype of `Double?` and `Int`); `.toDouble()` added at line 1160; committed `a8dd56f`.
- [x] **pr-test baseline confirmed**: Python 480 passed / 6 skipped; Android 36 tests / 1 pre-existing failure; Rust 114 passed.
- [x] **Rust CI working**: yebyen/mecris#142 fix confirmed applied by kingdonb — `working-directory` is correct in pr-test.yml.
- [x] **Plan issue closed**: yebyen/mecris#244 closed with completion comment.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Review and merge kingdonb/mecris#198**: 8 commits ready — obsidian parser + HeadlessLoopback + REMAINING TODAY + Majesty Cake + compile fix.
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure (`ExceptionInInitializerError` at line 35) — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [x] **Python test count investigation**: RESOLVED (yebyen/mecris#245). The 26-test gap was from an overstated baseline (claimed 464, actual ~437) + minor count errors. 480 is the correct passing count. No tests are broken.
- [ ] **Open next feature work**: After PR #198 merges, pick next kingdonb open issue for beta.2 feature work.

## New Features Landed in beta.2 dev cycle (since beta.1 baseline `90a569e`)

- **fix(android): Number/Double division type error in ReviewPumpWidget progress bar** (`a8dd56f`): `remainingToday.toDouble()` at line 1160 — resolves compile error from `Number` type inference. Contributes to kingdonb/mecris#198.
- **feat(android): Majesty Rings + all_clear state to MomentumVisualizer** (`96a3fb5`): `MomentumOrbState` enum, `momentumOrbState()` pure function, Gold/Green/Red color states, animated expanding rings overlay. 9 unit tests. Resolves yebyen/mecris#243, contributes to kingdonb/mecris#195.
- **feat(android): REMAINING TODAY counter backport** (`e30cda5`): `LanguageStatDto` gains `target_flow_rate`, `absolute_target`, `goal_met`; `ReviewPumpWidget` uses server value with GOAL MET badge. Resolves yebyen/mecris#242, contributes to kingdonb/mecris#194.
- **feat(ghost): HeadlessLoopback subprocess wrapper** (`0e50bb4`): `ghost/headless_loopback.py` — spawns `gemini --yolo`, captures stdout/stderr, SIGKILL timeout, 22 unit tests. Resolves kingdonb/mecris#197.
- **feat(obsidian): alternate checkbox styles in todo parser** (`ebe3d30`): Broaden regex to `[^\[\]]`; expose raw `status` char; add 20 unit tests. Resolves kingdonb/mecris#196.
- **feat(security): achieve SLSA Build Level 1** (`7d3d981`): Add `actions/attest-build-provenance` to Release workflow; generate signed provenance for APK and WASM; ROADMAP.md Alpha Hardening SLSA goals marked complete.
- **chore(config): remove --http flag from gemini MCP settings** (`b1d722e`): Beta testing config adjustment for Gemini MCP server.
- **chore(release): bump version to 0.0.1-beta.2** (`34d8582`): All 15+ ecosystem locations updated; dev cycle baseline set.
- **docs(beta): clear verified migration and double-counting items** (`27c665c`): NEXT_SESSION cleanup.
- **docs(auth): document VPN/Public Internet split as known issue** (`a10d988`): Auth docs update.

## Version Baseline (v0.0.1-beta.2 dev cycle)
- **Android**: 1.1.6-beta.2 (dev cycle bump)
- **Spin sync-service**: 0.3.1-beta.2
- **Python MCP**: 0.5.1-beta.2
- **Suite**: 0.0.1-beta.2
- **Web app**: Included in suite beta.2 bump

## Test Baseline (confirmed 2026-04-21 via pr-test on kingdonb/mecris#198)
- **Python**: 480 passed, 6 skipped (confirmed correct — baseline was ~437, not 464 as previously stated)
- **Android**: 36 tests total, 35 passing, 1 pre-existing PocketIdAuthTest failure (`ExceptionInInitializerError`)
- **Rust**: 114 passed (boris-fiona-walker + sync-service combined)

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
- **Rust satellite crates**: 99+ tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **bump_version.py now targets 15+ locations**: Covers Android, Spin, Python MCP, Web, and suite-level files.
- **SLSA Build Level 1**: `actions/attest-build-provenance` added to Release workflow. Signed provenance generated for APK + WASM artifacts.
- **Obsidian parser**: `_parse_todos_from_content` now uses `[^\[\]]` regex; returns `status` (raw char) + `completed` (bool). `ALTERNATE_CHECKBOX_CHARS` frozenset on class.
- **HeadlessLoopback**: `ghost/headless_loopback.py` — `HeadlessLoopback(command, timeout, log_output)` + `LoopbackResult(exit_code, stdout, stderr, timed_out, command)`. Default command: `["gemini", "--yolo"]`, default timeout: 1800s. `start_new_session=True` isolates child process group. 22 unit tests in `tests/test_headless_loopback.py`.
- **REMAINING TODAY backport**: `LanguageStatDto` fields `target_flow_rate: Double? = null`, `absolute_target: Int? = null`, `goal_met: Boolean = false`. `ReviewPumpWidget` uses `stat.target_flow_rate` with `ReviewPumpCalculator` fallback. GOAL MET badge shown when `goalMet == true`. Label "TARGET FLOW" removed; "REMAINING TODAY" replaces it.
- **MomentumVisualizer Majesty Cake**: `MomentumOrbState` enum (DEBT/STABLE/ALL_CLEAR); `momentumOrbState(momentum, isAllClear)` pure function; `MomentumVisualizer(isAllClear = ...)` param; Gold (#FFD600) orb + Majesty Rings (two animated expanding circles) when `all_clear == true`. 9 unit tests in `MomentumVisualizerTest.kt`.
- **ReviewPumpWidget progress bar type fix**: `remainingToday.toDouble()` at MainActivity.kt:1160 — `Number / Double` was ambiguous to Kotlin compiler; explicit cast resolves it.
- **Rust CI working-directory fixed**: yebyen/mecris#142 fix applied by kingdonb — `cargo test` runs from `mecris-go-spin/sync-service/`. 114 Rust tests passing in CI.
