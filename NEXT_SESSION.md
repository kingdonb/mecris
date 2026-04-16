# Next Session: Dispatch pr-test after 10b427a push; confirm Python ≥461

## Current Status (2026-04-16)
- **PR #184 still open on kingdonb/mecris** (yebyen:main → kingdonb:main): Now 5 commits ahead. Awaiting kingdonb review/merge.
- **15 new VirtualBudgetManager tests** committed at `10b427a` — `tests/test_virtual_budget_manager.py`. Expected Python baseline: **461** (446 + 15).
- **pr-test not yet dispatched**: push must land on GitHub before dispatch. Next session dispatches pr-test.
- **Satellite crate tests (147 total)**: In code but NOT yet in CI — requires workflow PAT fix (yebyen/mecris#142).
- **Akamai Functions (Trial)**: `sync-service` deployed. Cron jobs: `trigger-reminders` (2h), `failover-sync-edt` (04:05 UTC), `failover-sync-est` (05:05 UTC).

## Verified This Session
- [x] **PR #184 still open**: Confirmed open as of 2026-04-16T00:00Z — kingdonb/mecris at `94f2c54`.
- [x] **15 VirtualBudgetManager tests written and committed**: `10b427a` — closes yebyen/mecris#195 (partial, pending pr-test).

## Pending Verification (Next Session)
- [ ] **Dispatch pr-test for PR #184**: Run `/mecris-pr-test 184` after push lands — confirm Python ≥461 (446+15), Rust 91 ✅.
- [ ] **Confirm PR #184 merged by kingdonb**: Check kingdonb/mecris main for commits through `10b427a`.
- [ ] **Confirm Akamai cron jobs firing**: Check Akamai logs for `trigger-reminders`, `failover-sync-edt`, `failover-sync-est` executions.
- [ ] **Akamai E2E Logic Test**: Manually POST to `/internal/failover-sync` on Akamai endpoint.
- [ ] **Security Hardening (Akamai)**: Unauthenticated `/internal/*` endpoints need API key or IP whitelist.
- [ ] **Run 004_user_location.sql against live Neon**: `psql $NEON_DB_URL -f scripts/migrations/004_user_location.sql`.
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Multi-Tenancy — Android UI Gaps**: Add "log out" button, phone/location settings, preferred health source. Tracked in kingdonb/mecris#168.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT.
- [ ] **Multiplier Sync Validation**: Verify Android Review Pump lever updates `pump_multiplier` in Neon.

## Infrastructure Notes
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (POST): Unauthenticated sync for cron (Rust compile fix in `f5a4b09`).
  - `/internal/trigger-reminders` (POST): Unauthenticated reminder evaluation for cron.
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope.
- **Fine-grained PAT**: `GITHUB_TOKEN` scoped to yebyen/mecris only.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **Python venv not present in bot runner**: Validate Python tests via pr-test workflow only.
- **pr-test.yml push constraint**: Dispatch pr-test ONLY after commits land on GitHub (next session after push).
- **Rust satellite crates**: 91 tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **Rust compile fix pattern**: All branches in `handle_sync_service` that return a value must use explicit `return`. Bare `match` without `return` causes type error (expected `()`, found `Result<Response, _>`).
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, ...)` + `patch("psycopg2.connect")` before importing.
- **mcp_server handler test patterns** (`test_mcp_server_handlers.py`): Patch `mcp_server.resolve_target_user` for auth guard tests; patch `mcp_server.usage_tracker` for delegation tests; patch `mcp_server.weather_service` for weather tests.
- **VirtualBudgetManager test pattern**: Patch `virtual_budget_manager.credentials_manager.resolve_user_id` + omit `NEON_DB_URL` → no DB needed for pure/no-DB tests.
- **Python test count baseline**: 446 passed (4 skipped) as of pr-test run 24480880265. New commit adds 15 more; expected: **461**.
- **schema.sql budget_tracking schema**: columns are `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE REFERENCES users(pocket_id_sub)`.
- **Upstream sync pattern**: `git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD --no-edit`.
- **Groq-Beeminder sync**: kingdonb's `9bdf4e7` added automated @TARE reset logic and DB-backed identity resolution. Unit tests for Groq-Beeminder sync in `test_groq_beeminder_sync.py`.
