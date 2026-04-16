# Next Session: Dispatch pr-test for kingdonb/mecris#187 after push (now includes Profile Settings)

## Current Status (2026-04-16)
- **PR #187 open on kingdonb/mecris**: `feat(android): triggerReminders pulse when MCP is dark` — yebyen:main → kingdonb:main. Awaiting kingdonb review/merge.
- **6 new commits on yebyen:main since PR opened**: 3 from last session (triggerReminders) + 3 new (ProfilePreferencesManager + ProfileSettingsScreen). All 6 will be in the PR after push.
- **kingdonb/mecris main** still at `56dc719` — no new upstream commits.
- **yebyen:main is 6 commits ahead of kingdonb:main**: a26b53b (red), cc3336e (green), d8386af (archive-prev), 4cdabbb (red ProfilePrefs), 9c905e0 (green ProfilePrefs), 3e24f83 (feat ProfileSettings).
- **pr-test NOT YET dispatched for new commits**: last successful pr-test (run 24531480498) only covered triggerReminders, not ProfilePreferencesManager. New dispatch needed after push.

## Verified This Session
- [x] **kingdonb/mecris#180 Rust SQL ORDER BY**: already present in both repos at line 1242 of lib.rs — `ORDER BY start_time ASC`. Bug is fixed.
- [x] **HealthConnectManager preferred_health_source**: already reads from SharedPreferences (line 158). The fix was dead code — no UI to set the value.
- [x] **ProfilePreferencesManager.kt**: `mecris-go-project/app/src/main/java/com/mecris/go/profile/ProfilePreferencesManager.kt` — get/set for `preferred_health_source`, `phone_number`, `beeminder_user` from `mecris_app_prefs`.
- [x] **ProfilePreferencesManagerTest**: 8 unit tests (MockK pattern), committed `4cdabbb`.
- [x] **ProfileSettingsScreen composable**: OutlinedTextField for each pref, Save button, wired to Person icon in top bar, committed `3e24f83`.
- [x] **Plan issues closed**: yebyen/mecris#202 (already-fixed Rust ORDER BY), yebyen/mecris#203 commented with progress.

## Pending Verification (Next Session)
- [ ] **Dispatch pr-test for kingdonb/mecris#187** after workflow pushes yebyen:main. Expected: Python 461 passed (5 skipped), Rust 99 passed, Android BUILD SUCCESSFUL including 8 new `ProfilePreferencesManagerTest` cases + 2 CooperativeWorkerTest cases.
- [ ] **kingdonb/mecris#187 merged?** Check if kingdonb has merged. If yes: sync yebyen with `git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD --no-edit`.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. This activates the guard. (Needs human with Fermyon access.)
- [ ] **Run 005_autonomous_sync_consent.sql against live Neon**: `psql $NEON_DB_URL -f scripts/migrations/005_autonomous_sync_consent.sql`. (Needs human with NEON_DB_URL.)
- [ ] **Confirm Akamai cron jobs firing**: Check Akamai logs for `trigger-reminders`, `failover-sync-edt`, `failover-sync-est` executions.
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Multi-Tenancy — Android UI Gaps**: Add "log out" button, location/timezone settings. Tracked in kingdonb/mecris#168.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.
- [ ] **Multiplier Sync Validation**: Verify Android Review Pump lever updates `pump_multiplier` in Neon.

## Infrastructure Notes
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (POST): Now uses `handle_failover_sync_post()` — per-user consent flag + `last_autonomous_sync` tracking. Guarded by `internal_api_key` Spin variable (backwards compat: no key = allow all).
  - `/internal/trigger-reminders` (POST): Sends reminders only to users with `autonomous_sync_enabled = true`. Guarded by same key. Android now also calls this as best-effort pulse when MCP is dark.
- **triggerReminders design**: `SyncServiceApi.triggerReminders()` sends no auth header — Rust endpoint is gated by `X-Internal-Api-Key` only; with key unset (current), all callers are allowed. When key is set in Fermyon Cloud, only Akamai cron will have the key; Android pulse will gracefully fail with 401 (caught + logged).
- **ProfilePreferencesManager**: Reads/writes `mecris_app_prefs` SharedPreferences. Keys: `preferred_health_source`, `phone_number`, `beeminder_user`. Same SharedPreferences name as `HealthConnectManager` so both see the same value.
- **preferred_health_source flow**: User sets it in ProfileSettingsScreen → SharedPreferences → HealthConnectManager reads it on next `fetchRecentWalkData()` → AggregateRequest with `dataOriginFilter` set to that package name.
- **New migration**: `005_autonomous_sync_consent.sql` — adds `autonomous_sync_enabled BOOLEAN DEFAULT false` and `last_autonomous_sync TIMESTAMPTZ` to `users` table. Must run before live consent flag is effective.
- **Rust 99 tests**: 95 original + 4 new `is_autonomous_sync_allowed` tests. `internal_api_key_ok` tests also present (5 tests).
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope, no `read:org` (can't use `gh pr edit`).
- **Fine-grained PAT**: `GITHUB_TOKEN` scoped to yebyen/mecris only. Cannot create PRs on kingdonb/mecris — use `gh pr create` with `GITHUB_CLASSIC_PAT`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **Python venv not present in bot runner**: Validate Python tests via pr-test workflow only.
- **pr-test.yml push constraint**: Dispatch pr-test ONLY after commits land on GitHub (next session after push).
- **Rust satellite crates**: 99 tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **Rust compile fix pattern**: All branches in `handle_sync_service` that return a value must use explicit `return`. Bare `match` without `return` causes type error (expected `()`, found `Result<Response, _>`).
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, ...)` + `patch("psycopg2.connect")` before importing.
- **mcp_server handler test patterns** (`test_mcp_server_handlers.py`): Patch `mcp_server.resolve_target_user` for auth guard tests; patch `mcp_server.usage_tracker` for delegation tests; patch `mcp_server.weather_service` for weather tests.
- **VirtualBudgetManager test pattern**: Patch `virtual_budget_manager.credentials_manager.resolve_user_id` + omit `NEON_DB_URL` → no DB needed for pure/no-DB tests.
- **Python test count baseline**: 461 passed (5 skipped) confirmed in pr-test run 24531480498. Akamai E2E test now permanently skipped in CI.
- **schema.sql budget_tracking schema**: columns are `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE REFERENCES users(pocket_id_sub)`.
- **Upstream sync pattern**: `git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD --no-edit`.
- **Groq-Beeminder sync**: kingdonb's `9bdf4e7` added automated @TARE reset logic and DB-backed identity resolution. Unit tests for Groq-Beeminder sync in `test_groq_beeminder_sync.py`.
- **Akamai E2E test skip pattern**: `test_cron_validation.py::test_akamai_failover_sync_side_effect` skips when `NEON_DB_URL` contains `localhost` or `127.0.0.1`. Fix committed at `ed33d27`.
- **internal_api_key Spin variable**: Optional variable — set to activate `/internal/*` endpoint key guard. Header: `X-Internal-Api-Key`. Empty = open (backwards compat).
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders` and `/internal/failover-sync`. Default `false` — user must opt in.
