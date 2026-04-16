# Next Session: Dispatch pr-test for kingdonb/mecris#186 (now includes consent flag merge)

## Current Status (2026-04-16)
- **kingdonb/mecris#186 is still open**: PR from yebyen:main → kingdonb:main; awaiting kingdonb merge.
- **yebyen:main merged upstream**: `4d6e9d6` integrates kingdonb/mecris #185 (autonomous consent flag, 5 commits). Divergence resolved.
- **yebyen 6 commits ahead of kingdonb:main, 0 behind** ✅ (clean sync)
- **Rust test count: 99** (was 95; consent flag merge added 4 tests for `is_autonomous_sync_allowed`).
- **PR #186 net diff against kingdonb:main is clean**: Shows only yebyen additions — E2E skip guard + API key guard + `internal_api_key_ok` tests.

## Verified This Session
- [x] **Upstream sync complete**: Merged kingdonb/mecris main (PR #185, 5 commits) into yebyen:main via `4d6e9d6`.
- [x] **Merge conflict resolved**: `lib.rs` conflict resolved keeping BOTH API key guard (`16e8cb7`) AND per-user consent flag logic (#185).
- [x] **Rust 99 tests**: 95 previous + 4 new `is_autonomous_sync_allowed` tests from consent flag merge.
- [x] **yebyen/mecris#199 complete**: Plan issue closed.

## Pending Verification (Next Session)
- [ ] **Dispatch pr-test for PR #186**: Run `/mecris-pr-test 186` after CI pushes `4d6e9d6` to GitHub. Expect: 461 Python + 99 Rust pass.
- [ ] **kingdonb merges #186**: Confirm kingdonb/mecris#186 merged into main (includes E2E skip fix + API key guard + consent flag merge).
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. This activates the guard.
- [ ] **Sync yebyen after #186 merges**: `git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD --no-edit` (only after #186 is merged upstream).
- [ ] **Confirm Akamai cron jobs firing**: Check Akamai logs for `trigger-reminders`, `failover-sync-edt`, `failover-sync-est` executions.
- [ ] **Run 004_user_location.sql against live Neon**: `psql $NEON_DB_URL -f scripts/migrations/004_user_location.sql`.
- [ ] **Run 005_autonomous_sync_consent.sql against live Neon**: `psql $NEON_DB_URL -f scripts/migrations/005_autonomous_sync_consent.sql`. Adds `autonomous_sync_enabled` and `last_autonomous_sync` columns to `users` table.
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Multi-Tenancy — Android UI Gaps**: Add "log out" button, phone/location settings, preferred health source. Tracked in kingdonb/mecris#168.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT.
- [ ] **Multiplier Sync Validation**: Verify Android Review Pump lever updates `pump_multiplier` in Neon.

## Infrastructure Notes
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (POST): Now uses `handle_failover_sync_post()` — per-user consent flag + `last_autonomous_sync` tracking. Guarded by `internal_api_key` Spin variable (backwards compat: no key = allow all).
  - `/internal/trigger-reminders` (POST): Sends reminders only to users with `autonomous_sync_enabled = true`. Guarded by same key.
- **New migration**: `005_autonomous_sync_consent.sql` — adds `autonomous_sync_enabled BOOLEAN DEFAULT false` and `last_autonomous_sync TIMESTAMPTZ` to `users` table. Must run before live consent flag is effective.
- **Rust 99 tests**: 95 original + 4 new `is_autonomous_sync_allowed` tests. `internal_api_key_ok` tests also present (5 tests).
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope.
- **Fine-grained PAT**: `GITHUB_TOKEN` scoped to yebyen/mecris only.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **Python venv not present in bot runner**: Validate Python tests via pr-test workflow only.
- **pr-test.yml push constraint**: Dispatch pr-test ONLY after commits land on GitHub (next session after push).
- **Rust satellite crates**: 99 tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **Rust compile fix pattern**: All branches in `handle_sync_service` that return a value must use explicit `return`. Bare `match` without `return` causes type error (expected `()`, found `Result<Response, _>`).
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, ...)` + `patch("psycopg2.connect")` before importing.
- **mcp_server handler test patterns** (`test_mcp_server_handlers.py`): Patch `mcp_server.resolve_target_user` for auth guard tests; patch `mcp_server.usage_tracker` for delegation tests; patch `mcp_server.weather_service` for weather tests.
- **VirtualBudgetManager test pattern**: Patch `virtual_budget_manager.credentials_manager.resolve_user_id` + omit `NEON_DB_URL` → no DB needed for pure/no-DB tests.
- **Python test count baseline**: 461 passed (5 skipped) confirmed in pr-test run 24509446714. Akamai E2E test now permanently skipped in CI.
- **schema.sql budget_tracking schema**: columns are `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE REFERENCES users(pocket_id_sub)`.
- **Upstream sync pattern**: `git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD --no-edit`.
- **Groq-Beeminder sync**: kingdonb's `9bdf4e7` added automated @TARE reset logic and DB-backed identity resolution. Unit tests for Groq-Beeminder sync in `test_groq_beeminder_sync.py`.
- **Akamai E2E test skip pattern**: `test_cron_validation.py::test_akamai_failover_sync_side_effect` skips when `NEON_DB_URL` contains `localhost` or `127.0.0.1`. Fix committed at `ed33d27`.
- **internal_api_key Spin variable**: Optional variable — set to activate `/internal/*` endpoint key guard. Header: `X-Internal-Api-Key`. Empty = open (backwards compat).
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders` and `/internal/failover-sync`. Default `false` — user must opt in.
