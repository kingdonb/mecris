# Next Session: Open new PR + pr-test to confirm clean suite (0 failed, ≥461 passed)

## Current Status (2026-04-16)
- **PR #184 merged into kingdonb/mecris** at `dbdf626` — includes all commits through `2477c09` (VirtualBudgetManager 15 tests).
- **yebyen/mecris and kingdonb/mecris are in sync** (0 ahead, 0 behind).
- **pr-test run 24492032488**: Python **461 passed** ✅, Rust **91** ✅, Android ✅ — but **1 failure**: `test_akamai_failover_sync_side_effect` (E2E test against live Akamai that checks local postgres for side-effects — always wrong in CI).
- **Fix committed at `ed33d27`**: Added `localhost`/`127.0.0.1` check in `get_last_updated()` → test now skips in CI instead of failing. Not yet pushed.
- **yebyen/mecris#195 closed** (VirtualBudgetManager 15 tests — 461 confirmed).

## Verified This Session
- [x] **PR #184 merged by kingdonb**: Confirmed merged at `2026-04-16T02:33:58Z`, commit `dbdf626`.
- [x] **yebyen/mecris in sync with kingdonb/mecris**: `git rev-list` shows 0 ahead, 0 behind.
- [x] **Python 461 confirmed**: pr-test run 24492032488 — `461 passed, 4 skipped` (plus 1 E2E failure unrelated to VirtualBudgetManager).
- [x] **Rust 91 tests pass**: Confirmed in same run.
- [x] **VirtualBudgetManager 15 tests all passing**: Confirmed (461 = 446 + 15).
- [x] **Akamai E2E test root-caused**: `test_akamai_failover_sync_side_effect` hits live Akamai (writes to Neon) but queries local postgres (no ARABIC row) → always fails in CI. Pre-existing design issue.

## Pending Verification (Next Session)
- [ ] **Open new PR from yebyen:main → kingdonb:main** with `ed33d27` (E2E skip fix). Push lands automatically via workflow after this session.
- [ ] **Dispatch pr-test for the new PR**: Confirm Python ≥461 passed, **0 failed** (was 1 failed before fix). Expected: 461 passed, 5 skipped.
- [ ] **Confirm Akamai cron jobs firing**: Check Akamai logs for `trigger-reminders`, `failover-sync-edt`, `failover-sync-est` executions.
- [ ] **Akamai E2E Logic Test**: Manually POST to `/internal/failover-sync` on Akamai endpoint (use live Neon NEON_DB_URL to verify side effects).
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
- **Python test count baseline**: 461 passed (4 skipped) confirmed in pr-test run 24492032488. After `ed33d27` fix, expect **461 passed, 5 skipped** (E2E test now skips in CI).
- **schema.sql budget_tracking schema**: columns are `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE REFERENCES users(pocket_id_sub)`.
- **Upstream sync pattern**: `git fetch https://github.com/kingdonb/mecris.git main && git merge FETCH_HEAD --no-edit`.
- **Groq-Beeminder sync**: kingdonb's `9bdf4e7` added automated @TARE reset logic and DB-backed identity resolution. Unit tests for Groq-Beeminder sync in `test_groq_beeminder_sync.py`.
- **Akamai E2E test skip pattern**: `test_cron_validation.py::test_akamai_failover_sync_side_effect` skips when `NEON_DB_URL` contains `localhost` or `127.0.0.1`. Fix committed at `ed33d27`.
