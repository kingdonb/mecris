# Next Session: pr-test to validate Majesty Cake + confirm baseline (session #19 archived)

## Current Status (2026-04-21, post-session #19, plan yebyen/mecris#243)
- **Repos ahead of kingdonb**: yebyen/mecris is now 7 commits ahead — obsidian parser + HeadlessLoopback + REMAINING TODAY backport + Majesty Cake; needs PR to kingdonb.
- **kingdonb/mecris HEAD**: `6157f5f` (docs(agent): introduce Empty Backlog Protocol to prevent doom-looping) — NOT yet in yebyen; yebyen also needs to merge this upstream commit.
- **Beta.2 dev cycle open**: Suite version at `v0.0.1-beta.2`.
- **Majesty Cake implemented**: `MomentumVisualizer` now has `isAllClear` param, three-state color palette (Gold/Green/Red), and Majesty Rings (two animated expanding gold circles on non-rotating Canvas overlay).
- **9 unit tests added**: `MomentumVisualizerTest.kt` covers `momentumOrbState()` state transitions and boundary conditions — syntax-verified, not yet run via pr-test.

## Verified This Session (2026-04-21, plan yebyen/mecris#243)
- [x] **Plan issue opened**: yebyen/mecris#243 — recorded before touching any code.
- [x] **MomentumOrbState enum added**: `DEBT / STABLE / ALL_CLEAR` — pure testable type.
- [x] **momentumOrbState() function added**: pure function, no Compose dependency, drives color derivation.
- [x] **MomentumVisualizer extended**: `isAllClear: Boolean = false` param; Gold/Green/Red colors; Majesty Rings on non-rotating overlay Canvas.
- [x] **Call site updated**: `MainNeuralDashboard` passes `isAllClear = aggregateStatus?.all_clear == true`.
- [x] **Commit `96a3fb5`**: `feat(android): add Majesty Rings + all_clear state to MomentumVisualizer (kingdonb#195)` — committed successfully.
- [x] **Plan issue closed**: yebyen/mecris#243 closed with completion comment.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Open PR to kingdonb/mecris**: yebyen is now 7 commits ahead — human should review and merge obsidian parser + headless loopback + REMAINING TODAY + Majesty Cake.
- [ ] **Merge upstream commit**: kingdonb `6157f5f` (Empty Backlog Protocol docs) is NOT in yebyen — needs human merge or bot sync when PAT scope allows.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Confirm Python+Android test baseline via pr-test**: Estimated ~506 Python (464 baseline + 20 obsidian + 22 headless_loopback) + Android tests (~27 total + 9 new MomentumVisualizerTest = ~36, minus 1 pre-existing PocketIdAuthTest failure). Verify on next PR test run.
- [ ] **Sync upstream `6157f5f` from kingdonb**: Bot can fetch and merge if a PR can be opened against yebyen fork, or via fetch+commit pattern.

## New Features Landed in beta.2 dev cycle (since beta.1 baseline `90a569e`)

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
- **Python test count baseline**: ~464 passed (6 skipped), 0 failing + 20 new in test_obsidian_parser.py + 22 new in test_headless_loopback.py (both syntax-verified only). Rust: 108 passed. Android: ~27 tests (1 pre-existing PocketIdAuthTest failure) + 9 new in MomentumVisualizerTest.kt (syntax-verified).
- **Rust satellite crates**: 99+ tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **bump_version.py now targets 15+ locations**: Covers Android, Spin, Python MCP, Web, and suite-level files.
- **SLSA Build Level 1**: `actions/attest-build-provenance` added to Release workflow. Signed provenance generated for APK + WASM artifacts.
- **Obsidian parser**: `_parse_todos_from_content` now uses `[^\[\]]` regex; returns `status` (raw char) + `completed` (bool). `ALTERNATE_CHECKBOX_CHARS` frozenset on class.
- **HeadlessLoopback**: `ghost/headless_loopback.py` — `HeadlessLoopback(command, timeout, log_output)` + `LoopbackResult(exit_code, stdout, stderr, timed_out, command)`. Default command: `["gemini", "--yolo"]`, default timeout: 1800s. `start_new_session=True` isolates child process group. 22 unit tests in `tests/test_headless_loopback.py`.
- **REMAINING TODAY backport**: `LanguageStatDto` fields `target_flow_rate: Double? = null`, `absolute_target: Int? = null`, `goal_met: Boolean = false`. `ReviewPumpWidget` uses `stat.target_flow_rate` with `ReviewPumpCalculator` fallback. GOAL MET badge shown when `goalMet == true`. Label "TARGET FLOW" removed; "REMAINING TODAY" replaces it.
- **MomentumVisualizer Majesty Cake**: `MomentumOrbState` enum (DEBT/STABLE/ALL_CLEAR); `momentumOrbState(momentum, isAllClear)` pure function; `MomentumVisualizer(isAllClear = ...)` param; Gold (#FFD600) orb + Majesty Rings (two animated expanding circles) when `all_clear == true`. 9 unit tests in `MomentumVisualizerTest.kt`.
