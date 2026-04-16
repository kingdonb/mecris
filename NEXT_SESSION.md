# Next Session: Android App Feature Review & "Grill-Me" Session (Moussaka issue)

## Current Status (2026-04-16)
- **Akamai Cloud Sync Resolved**: The `spin aka cron` triggers are fully functional. Found and fixed HTTP method mismatch (allowing GET for cron), applied missing `004_user_location.sql` migration to live Neon, and successfully encrypted the Twilio auth token.
- **Architectural Update**: Implemented the "Cheap Settlement" (Delegated-Agent pattern). The `/internal/*` routes are guarded by a global `internal_api_key` (currently unset for backwards compatibility) AND a mandatory per-user DB consent flag (`autonomous_sync_enabled`). DoS risks are mitigated via a 5-minute debounce check (`last_autonomous_sync`).
- **Groq Integration**: Due to Groq API limitations (interactive OAuth required for usage data), the background cron integration for the odometer is infeasible. The Python MCP tool (`record_groq_reading`) remains the architectural standard.
- **PR #187 open on kingdonb/mecris**: Includes the Android Profile Settings screen (which fixes #180 by making `preferred_health_source` settable) and `triggerReminders`. Awaiting kingdonb review/merge.
- **Test Baseline**: Python: 461 passed (5 skipped). Rust: 99 passed. Android: BUILD SUCCESSFUL (including 8 new `ProfilePreferencesManagerTest` cases).

## Verified This Session
- [x] **Cron Configuration**: The cron schedule triggers endpoints using `GET` requests, which are now correctly handled by the Rust `sync-service`.
- [x] **Live Neon Schema**: The `users` table now contains `location_lat`, `location_lon`, `autonomous_sync_enabled`, and `last_autonomous_sync`.
- [x] **Cron Security**: The `/internal/failover-sync` and `/internal/trigger-reminders` routes check for both the `X-Internal-Api-Key` and the user's `autonomous_sync_enabled` flag.
- [x] **Akamai Deployment Success**: The `sync-service` successfully executes the Clozemaster web scraping loop when triggered via the cron endpoint.

## Pending Verification (Next Session)
- [ ] **Android App Spec & "Grill-Me" Session**: Prepare a spec for the Android app core features. Investigate the "moussaka in the morning" notification issue to determine if there are logic flaws in the Majesty Cake or Review Pump notifications.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. (Needs human with Fermyon access.)
- [ ] **Dispatch pr-test for kingdonb/mecris#187** after workflow pushes yebyen:main. Expected: Python 461 passed (5 skipped), Rust 99 passed, Android BUILD SUCCESSFUL.
- [ ] **kingdonb/mecris#187 merged?** Check if kingdonb has merged. If yes: sync yebyen with `git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD --no-edit`.
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Multi-Tenancy — Android UI Gaps**: Add "log out" button, location/timezone settings. Tracked in kingdonb/mecris#168.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.

## Infrastructure Notes
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (GET/POST): Now uses `handle_failover_sync_post()` — per-user consent flag + `last_autonomous_sync` tracking. Guarded by `internal_api_key` Spin variable (backwards compat: no key = allow all).
  - `/internal/trigger-reminders` (GET/POST): Sends reminders only to users with `autonomous_sync_enabled = true`. Guarded by same key. Android now also calls this as best-effort pulse when MCP is dark.
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
- **internal_api_key Spin variable**: Optional variable — set to activate `/internal/*` endpoint key guard. Header: `X-Internal-Api-Key`. Empty = open (backwards compat).
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders` and `/internal/failover-sync`. Default `false` — user must opt in.
