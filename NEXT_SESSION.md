# Next Session: PR #184 (kingdonb/mecris) awaiting kingdonb review/merge

## Current Status (2026-04-15)
- **PR #184 open on kingdonb/mecris** (yebyen:main → kingdonb:main): Contains Rust fix (`f5a4b09`), 9 Python handler tests (`f568c15`), archive commit (`993c4b3`). Awaiting kingdonb review/merge.
- **pr-test run 24480880265**: Python **446 ✅**, Rust **91 ✅**, Android ✅ — all green. Validation complete.
- **yebyen/mecris is 3 commits ahead of kingdonb/mecris**: `f5a4b09`, `f568c15`, `993c4b3` pending in PR #184.
- **Satellite crate tests (147 total)**: In code but NOT yet in CI — requires workflow PAT fix (yebyen/mecris#142).
- **Akamai Functions (Trial)**: `sync-service` deployed. Cron jobs: `trigger-reminders` (2h), `failover-sync-edt` (04:05 UTC), `failover-sync-est` (05:05 UTC).

## Verified This Session
- [x] **PR #182 merged by kingdonb**: Confirmed merged at `1aabc8f5` (2026-04-15T20:12:10Z).
- [x] **PR #184 created**: kingdonb/mecris#184 (yebyen:main → kingdonb:main) — 3 commits ahead.
- [x] **pr-test run 24480880265**: Python **446 passed, 4 skipped** ✅ — 9 new tests confirmed counted.
- [x] **Rust fix verified in CI**: 91 Rust tests pass ✅ (`f5a4b09` resolves compile error from `be513c92`).

## Pending Verification (Next Session)
- [ ] **Confirm PR #184 merged by kingdonb**: Check kingdonb/mecris main for commits through `993c4b3`.
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
- **Python test count baseline**: 446 passed (4 skipped) as of pr-test run 24480880265. New baseline: **446**.
- **schema.sql budget_tracking schema**: columns are `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE REFERENCES users(pocket_id_sub)`.
- **Upstream sync pattern**: `git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD --no-edit`.
- **Groq-Beeminder sync**: kingdonb's `9bdf4e7` added automated @TARE reset logic and DB-backed identity resolution. Unit tests for Groq-Beeminder sync in `test_groq_beeminder_sync.py`.
