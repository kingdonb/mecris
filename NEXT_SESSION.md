# Next Session: kingdonb review and merge of kingdonb/mecris#178 + Twilio integration test

## Current Status (2026-04-11)
- **PR open upstream**: kingdonb/mecris#178 from yebyen:main — 14 Rust unit tests + 3 cloud-sync Python tests + schema fixes + test isolation fixes. Not yet merged.
- **Python CI fully green**: pr-test run 24269477437 — 321 passed, 4 skipped, 0 failures. Confirmed green again this session (matches prior run 24252329711).
- **Android CI green**: unchanged from prior sessions.
- **Rust CI still failing**: Known; `pr-test.yml` runs `cargo test` in wrong directory. Exact fix documented in yebyen/mecris#142. Needs `workflow` PAT scope to apply — bot cannot push workflow file changes.
- **yebyen/mecris ahead of kingdonb/mecris**: All divergence is in PR #178 + `3a6d5f3` (Twilio helpers) + `5ba5b96` (send_walk_reminder).
- **All Rust crates pass locally**: sync-service now has 22 tests (was 18). Total across 6 crates: 55 tests, all green.
- **Twilio Phase 2 complete (unit-testable layer)**: `send_walk_reminder`, `build_sms_request_parts`, and fully wired `handle_trigger_reminders_post` added in `5ba5b96`. Integration test requires live Spin env.

## Verified This Session
- [x] **send_walk_reminder implemented (2026-04-11)**: Pure function `build_sms_request_parts` + async `send_walk_reminder` + full `handle_trigger_reminders_post` handler. 4 new tests, 22 total. Commit `5ba5b96`. Closes yebyen/mecris#148.
- [x] **Twilio SMS helpers ported to sync-service (2026-04-11)**: 3 pure functions + route stub + 4 new tests. `cargo test` passes 18 tests. Commit `3a6d5f3`. Closes yebyen/mecris#146.
- [x] **All open kingdonb/mecris issues scanned (2026-04-11, 2nd run)**: Full issue list reviewed — 20 open issues, all are epics/arch discussions/Android/WASM/live-env tasks. No new bot-actionable backend Python work found. Majesty Cake backend complete, reminder service complete (1156 lines of tests), test suite at 321+ passing. Nothing new to implement.
- [x] **PR #178 still open, upstream still stalled (2026-04-11)**: Orient confirmed kingdonb/mecris upstream has not moved since `ab7fef7` (2026-04-09). No new commits, no new issues. PR #178 still awaiting review. No new bot-actionable work.
- [x] **pr-test #178 still green (re-confirmed)**: run 24269477437 — 321 passed, 4 skipped, 0 failures. Python ✅ Android ✅. (2026-04-10)
- [x] **pr-test #178 Python tests fully green**: run 24252329711 — 321 passed, 4 skipped, 0 failures. (Verified prior session; still holds.)
- [x] **test_narrator_context_standalone is SAFE**: Audited and confirmed in yebyen/mecris#140. (Verified prior session.)
- [x] **Rust workflow fix documented**: yebyen/mecris#142 created with exact `working-directory: mecris-go-spin/sync-service` diff. Verified `Cargo.toml` exists at that path.
- [x] **No upstream sync needed**: yebyen is AHEAD of kingdonb. kingdonb's latest is `ab7fef7` (merge commit, 2026-04-09).
- [x] **All 6 Rust crates pass natively**: sync-service (22), review-pump (17), majesty-cake-rs (4), nag-engine-rs (4), review-pump-rs (4), goal-type-rs (5) — 55 total, all green.
- [x] **review-pump test bug fixed**: `flow_state_turbulent_when_at_or_above_target` had wrong assertion `target_flow_rate == 60`; corrected to `0`. Commit `53b4fd7`. Closes yebyen/mecris#143.

## Pending Verification (Next Session)
- [ ] **PR kingdonb/mecris#178 merged**: Python + Android are green (re-confirmed 2026-04-10 run 24269477437). Rust is a known pre-existing gap with documented fix in yebyen/mecris#142. Needs kingdonb review and merge.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142: add `working-directory: mecris-go-spin/sync-service` to `Run Rust tests` step in `.github/workflows/pr-test.yml`. Needs `workflow` PAT scope or kingdonb direct action.
- [ ] **After PR #178 merge: sync yebyen from upstream**: `git fetch upstream && git merge upstream/main --no-edit`. Then verify yebyen is up to date.
- [ ] **send_walk_reminder integration test**: The HTTP dispatch (`spin_sdk::http::send`) in `send_walk_reminder` cannot be unit-tested without Spin host. Verify by deploying to Spin Cloud and triggering `POST /internal/trigger-reminders` with a configured `twilio_account_sid`, `twilio_auth_token_encrypted`, `twilio_from_number` in `spin.toml` variables.
- [ ] **Twilio Spin variables not yet configured**: `twilio_account_sid`, `twilio_auth_token_encrypted`, `twilio_from_number` must be added to `spin.toml` (or `.spin/config.toml`) before the reminder endpoint is functional in a live deployment. These are not in the repo — must be set by kingdonb in the live environment.
- [ ] **Multiplier Sync Validation**: Verify setting the Review Pump lever in Android updates multiplier in Neon (`SELECT pump_multiplier FROM language_stats`). Requires live device + Neon access.
- [ ] **Ghost Archivist End-to-End**: Run scheduler locally, let archivist job fire, confirm logs show correct reconciliation without pushing fake data to Beeminder. (Unit tests complete; E2E still needs live environment.)
- [ ] **kingdonb/mecris#132 verification**: Trigger `/internal/failover-sync` and confirm `daily_completions` is non-zero in Neon if reviews were done.
- [ ] **kingdonb/mecris#127 manual close**: Bot cannot comment/close kingdonb issues (PAT scoped to yebyen only). kingdonb should close #127 as superseded by #132.
- [ ] **Android app has_goal UI**: Confirm Android app picks up `has_goal=false` flag and visually dims untracked languages. Requires live app test.
- [ ] **Majesty Cake Android integration**: `/aggregate-status` backend complete; Android app needs to consume it (kingdonb/mecris#170).
- [ ] **003_multi_tenancy.sql live run**: Run `psql $NEON_DB_URL -f scripts/migrations/003_multi_tenancy.sql` against live Neon.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope. Workflow file fixes must be committed by kingdonb or a token with `workflow` scope.
- **Fine-grained PAT**: `GITHUB_TOKEN` is scoped to yebyen/mecris only — cannot comment or close issues on kingdonb/mecris.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main resolves this automatically.
- **psycopg2 not installed in CI runner**: `test_presence_neon.py` may have pre-existing failures — not a regression.
- **Python venv not present in bot runner**: `PYTHONPATH=. .venv/bin/pytest` cannot run in bot context; Python tests validated via kingdonb/mecris pr-test workflow instead.
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, ...)` + `patch("psycopg2.connect")` before importing. See `_make_mcp_importable()` in `test_mcp_server.py`, `test_cloud_sync.py`, `test_standalone_access.py`, `test_unauthorized_access.py`, `test_walk_sync.py`.
- **standalone test safety**: `_record_presence` (mcp_server.py:46-54) is fully guarded — returns None if no store, wraps upsert in try/except. Main handler (mcp_server.py:367-490) has outer try/except that returns dict on failure. `/narrator/context` always returns HTTP 200 in standalone mode.
- **Ghost Archivist lazy-import pattern**: `BeeminderClient` and `LanguageSyncService` are imported INSIDE `perform_archival_sync()` function body. Patch at source modules, not at `ghost.archivist_logic`.
- **cloud-sync patch pattern**: `language_sync_service` is a module-level variable. Use `patch("mcp_server.language_sync_service")` AFTER importing mcp_server within env+psycopg2 patches.
- **BeeminderClient note**: `UsageTracker.__init__` requires `NEON_DB_URL` even in the no-DB fallback path — mock UsageTracker when testing the env-var-only path.
- **Multi-tenancy schema**: `language_stats` PK is `(user_id, language_name)`; `budget_tracking` has `user_id UNIQUE` with FK to `users(pocket_id_sub)`. All queries scope by user_id.
- **pr-test workflow sets NEON_DB_URL** (line 93 of pr-test.yml): `postgresql://mecris:mecris@localhost:5432/mecrisdb`. Tests that import mcp_server MUST patch psycopg2.connect or they will try to connect to the real local postgres and hit FK constraints.
- **schema.sql budget_tracking schema**: Fixed in `8597dbe` — columns are now `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE REFERENCES users(pocket_id_sub)`.
- **schema.sql token_bank**: Added in `c88d368` — `CREATE TABLE IF NOT EXISTS token_bank (user_id TEXT PRIMARY KEY REFERENCES users(pocket_id_sub), available_tokens BIGINT NOT NULL DEFAULT 0, monthly_limit BIGINT NOT NULL DEFAULT 1000000, last_refill TIMESTAMPTZ NOT NULL DEFAULT NOW())`.
- **requirements.txt Python dep chain**: `apscheduler>=3.10` + `SQLAlchemy>=2.0` — both needed because `scheduler.py` imports `SQLAlchemyJobStore` from apscheduler.
- **Upstream sync pattern**: `git remote add upstream https://github.com/kingdonb/mecris.git && git fetch upstream main && git merge upstream/main --no-edit`.
- **Rust unit tests**: Pure functions extracted to module scope — `cargo test` in `mecris-go-spin/sync-service/` runs 22 tests natively without Spin host. New in `5ba5b96`: `build_sms_request_parts` (4 tests) + existing 18.
- **Rust workspace**: No workspace Cargo.toml in `mecris-go-spin/`. `sync-service` has `[workspace]` making it self-contained (can't join a parent workspace). Each crate must be tested individually. 6 crates, 55 tests total.
- **Rust workflow fix**: Add `working-directory: mecris-go-spin/sync-service` to `Run Rust tests` step in pr-test.yml. Exact diff in yebyen/mecris#142. Cannot push (no workflow PAT). Additional crates need separate CI steps.
- **pr-test.yml push constraint**: Bot dispatches pr-test but local commits are not on GitHub until bot workflow ends. Do NOT dispatch pr-test expecting to see local commits — always dispatch AFTER the push (i.e., in the NEXT session after commits land).
- **target_flow_rate semantics**: This field means "remaining work to reach target" = `(target - daily_completions).max(0)`. When at or above target, value is 0. See `services/review_pump.py:67` and `mecris-go-spin/review-pump/src/lib.rs:114`.
- **Twilio helpers in sync-service**: `build_twilio_url`, `build_twilio_body`, `encode_basic_auth`, `build_sms_request_parts` are pure functions at module scope in `lib.rs`. `send_walk_reminder` is async and requires Spin host to dispatch. `handle_trigger_reminders_post` reads `twilio_account_sid`, `twilio_auth_token_encrypted`, `twilio_from_number` from Spin variables.
- **phone_number_encrypted column**: Exists in `users` table per `scripts/migrations/002_pii_encryption.sql` and `mecris-go-spin/schema.sql`. The trigger-reminders handler queries all users with this column set.
