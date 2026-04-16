# Next Session: Await merge of kingdonb/mecris#187 (triggerReminders), then sync yebyen

## Current Status (2026-04-16)
- **PR #187 open on kingdonb/mecris**: `feat(android): triggerReminders pulse when MCP is dark` — yebyen:main → kingdonb:main. Awaiting kingdonb review/merge.
- **pr-test run 24531480498**: ✅ success — Python 461 passed (5 skipped), Android BUILD SUCCESSFUL (24 tasks, all CooperativeWorkerTest pass), Rust 99 passed.
- **yebyen:main is 3 commits ahead of kingdonb:main**: a26b53b (red), cc3336e (green), d8386af (archive). PR #187 carries all three.
- **Rust test count**: 99 (95 + 4 `is_autonomous_sync_allowed` tests). Android unit tests include 2 new CooperativeWorkerTest cases.

## Verified This Session
- [x] **PR #187 opened**: kingdonb/mecris#187 `feat(android): triggerReminders pulse when MCP is dark`.
- [x] **pr-test passed**: run 24531480498 — Python ✅, Android ✅, Rust ✅.
- [x] **2 new CooperativeWorkerTest cases** confirmed passing in Android test suite.
- [x] **Plan yebyen/mecris#201 complete**: closed.

## Pending Verification (Next Session)
- [ ] **kingdonb/mecris#187 merged?** Check if kingdonb has merged. If yes: sync yebyen with `git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD --no-edit`.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. This activates the guard. (Needs human with Fermyon access.)
- [ ] **Run 005_autonomous_sync_consent.sql against live Neon**: `psql $NEON_DB_URL -f scripts/migrations/005_autonomous_sync_consent.sql`. Adds `autonomous_sync_enabled` and `last_autonomous_sync` columns to `users` table. (Needs human with NEON_DB_URL.)
- [ ] **Confirm Akamai cron jobs firing**: Check Akamai logs for `trigger-reminders`, `failover-sync-edt`, `failover-sync-est` executions.
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Multi-Tenancy — Android UI Gaps**: Add "log out" button, phone/location settings, preferred health source. Tracked in kingdonb/mecris#168.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.
- [ ] **Multiplier Sync Validation**: Verify Android Review Pump lever updates `pump_multiplier` in Neon.

## Infrastructure Notes
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (POST): Now uses `handle_failover_sync_post()` — per-user consent flag + `last_autonomous_sync` tracking. Guarded by `internal_api_key` Spin variable (backwards compat: no key = allow all).
  - `/internal/trigger-reminders` (POST): Sends reminders only to users with `autonomous_sync_enabled = true`. Guarded by same key. Android now also calls this as best-effort pulse when MCP is dark.
- **triggerReminders design**: `SyncServiceApi.triggerReminders()` sends no auth header — Rust endpoint is gated by `X-Internal-Api-Key` only; with key unset (current), all callers are allowed. When key is set in Fermyon Cloud, only Akamai cron will have the key; Android pulse will gracefully fail with 401 (caught + logged).
- **New migration**: `005_autonomous_sync_consent.sql` — adds `autonomous_sync_enabled BOOLEAN DEFAULT false` and `last_autonomous_sync TIMESTAMPTZ` to `users` table. Must run before live consent flag is effective.
- **Rust 99 tests**: 95 original + 4 new `is_autonomous_sync_allowed` tests. `internal_api_key_ok` tests also present (5 tests).
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope.
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
