# Next Session: Run pr-test to verify Rust fix + 446 Python baseline (f568c15)

## Current Status (2026-04-15)
- **PR #182 open on kingdonb/mecris** (yebyen:main → kingdonb:main): Awaiting kingdonb review/merge.
- **pr-test run 24475982299**: Python 437 ✅, Android ✅, Rust ❌ (compile error in kingdonb's `be513c92` — missing `return` before `match` in `/internal/failover-sync` handler).
- **Rust compile error FIXED**: `f5a4b09` adds `return` before the `match` in `handle_sync_service` failover-sync branch. Fix compiles clean (91 tests pass locally). Needs pr-test to confirm in CI.
- **9 new Python tests committed** at `f568c15` — `get_recent_usage`, `get_weather_full_report`, `add_goal`, `update_budget`, `complete_goal` (auth guard + delegation). Expected Python count: **446** (437 + 9).
- **yebyen/mecris is ahead of kingdonb/mecris**: kingdonb merged yebyen at `1aabc8f5`, then added `be513c92` + `94f2c543`; bot added `f5a4b09` + `f568c15` on top.
- **Akamai Functions (Trial)**: `sync-service` deployed. Cron jobs: `trigger-reminders` (2h), `failover-sync-edt` (04:05 UTC), `failover-sync-est` (05:05 UTC).
- **Satellite crate tests (147 total)**: In code but NOT yet in CI — requires workflow PAT fix (yebyen/mecris#142).

## Verified This Session
- [x] **pr-test run 24475982299**: Python **437 passed, 4 skipped** — baseline confirmed.
- [x] **Rust compile error root-caused**: kingdonb's `be513c92` (`/internal/failover-sync` route) missing `return` before `match run_clozemaster_scraper(...)`.
- [x] **Rust fix committed** at `f5a4b09`: `return match ...;` — 91 sync-service tests pass locally.
- [x] **9 new mcp_server handler tests committed** at `f568c15`: covers `get_recent_usage`, `get_weather_full_report`, `add_goal`, `update_budget`, `complete_goal`.

## Pending Verification (Next Session)
- [ ] **Dispatch pr-test for PR #182 (or latest yebyen:main) to verify**: Rust should now pass (fix in `f5a4b09`); Python should show **446** (9 new tests in `f568c15`). Run ID from this session: 24475982299 (pre-fix). Next session's run should show Rust ✅.
- [ ] **Confirm PR #182 merged by kingdonb**: Check kingdonb/mecris main for commits through `f568c15`.
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
- **Python test count baseline**: 437 passed (4 skipped) as of pr-test run 24475982299. Expected after `f568c15`: **446 passed**.
- **schema.sql budget_tracking schema**: columns are `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE REFERENCES users(pocket_id_sub)`.
- **Upstream sync pattern**: `git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD --no-edit`.
- **Groq-Beeminder sync**: kingdonb's `9bdf4e7` added automated @TARE reset logic and DB-backed identity resolution. Unit tests for Groq-Beeminder sync in `test_groq_beeminder_sync.py`.
