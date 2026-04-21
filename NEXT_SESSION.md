# Next Session: Obsidian parser enhanced — run pr-test to validate Python baseline (beta.2 dev cycle, session #16 archived)

## Current Status (2026-04-21, post-session #16, plan yebyen/mecris#240)
- **Repos ahead of kingdonb**: yebyen/mecris is now 1 commit ahead (`ebe3d30`) with the Obsidian parser enhancement — needs PR to kingdonb.
- **kingdonb/mecris HEAD**: `6157f5f` (docs(agent): introduce Empty Backlog Protocol to prevent doom-looping)
- **Beta.2 dev cycle open**: Suite version at `v0.0.1-beta.2`.
- **Obsidian parser enhanced**: `_parse_todos_from_content` now recognizes alternate checkbox styles (`[>]`, `[<]`, `[?]`, `[-]`, `[!]`, `/`) plus exposes raw `status` character.
- **20 unit tests added**: `tests/test_obsidian_parser.py` — validated via syntax check only (no venv in bot runner); pr-test will confirm.

## Verified This Session (2026-04-21, plan yebyen/mecris#240)
- [x] **Plan issue opened**: yebyen/mecris#240 — recorded before touching any code.
- [x] **obsidian_client.py updated**: regex broadened from `[ x]` to `[^\[\]]`; `status` field added to returned dicts; `ALTERNATE_CHECKBOX_CHARS` class constant added; `get_todos()` searches for `[>]` and `[-]` patterns in addition to `[ ]` and `[x]`.
- [x] **tests/test_obsidian_parser.py created**: 20 unit tests across 4 test classes; syntax verified clean.
- [x] **Commit `ebe3d30`**: `feat(obsidian): support alternate checkbox styles in todo parser (kingdonb#196)` — committed successfully.
- [x] **Plan issue closed**: yebyen/mecris#240 closed with completion comment.
- [x] **Health report yebyen#239**: Still open (prior session health report — needs closing next session if not already done by workflow).

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing debouncing tests over endpoint auth.
- [ ] **Open PR to kingdonb/mecris**: yebyen is now 1 commit ahead with obsidian parser enhancement — human should review and merge.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Close yebyen#239**: Prior health report — close it now that session #16 produced real work.
- [ ] **Confirm Python test baseline via pr-test**: Estimated ~464 passed (unchanged), plus 20 new tests in `test_obsidian_parser.py`. Verify on next PR test run.
- [ ] **Backport "REMAINING TODAY" counter (Issue #194)**: Update `LanguageStatDto` and `ReviewPumpWidget` in Android app to match Web UI "remaining" count logic.
- [ ] **Backport "Majesty Cake" Visualizer (Issue #195)**: Implement pulsing orb and Majesty Rings in Jetpack Compose for the Android app.
- [ ] **Implement Headless Loopback wrapper (Issue #197)**: Create a subprocess wrapper for `gemini --yolo` with timeout limits to enable background autonomous turns.

## New Features Landed in beta.2 dev cycle (since beta.1 baseline `90a569e`)

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
- **Python test count baseline**: ~464 passed (6 skipped), 0 failing + 20 new in test_obsidian_parser.py (syntax-verified only). Rust: 108 passed. Android: 27 tests (1 pre-existing failure).
- **Rust satellite crates**: 99+ tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **bump_version.py now targets 15+ locations**: Covers Android, Spin, Python MCP, Web, and suite-level files.
- **SLSA Build Level 1**: `actions/attest-build-provenance` added to Release workflow. Signed provenance generated for APK + WASM artifacts.
- **Obsidian parser**: `_parse_todos_from_content` now uses `[^\[\]]` regex; returns `status` (raw char) + `completed` (bool). `ALTERNATE_CHECKBOX_CHARS` frozenset on class.
