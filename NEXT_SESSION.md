# Next Session: Open PR from yebyen:main → kingdonb:main (2 commits ahead) to validate pr-test count

## Current Status (2026-04-13)
- **yebyen/mecris is 2 commits ahead of kingdonb:main**: `e0b71d1` (archive) + `20cfc7b` (delete_user_data feat) not yet in upstream. `git rev-list HEAD..upstream/main` = 0. `git rev-list upstream/main..HEAD` = 2.
- **delete_user_data MCP tool added (2026-04-13)**: Commit `20cfc7b` — `mcp_server.py` now has `delete_user_data()` tool. FK-safe: deletes `token_bank` first, then `users` (CASCADE handles rest). Tests in `tests/test_delete_user_data.py` (4 tests). Closes GDPR right-to-erasure gap.
- **SMSConsentManager tests (22)**: 21 from `e0acfe4` + 1 cross-instance reload from `1b3cd4f`. In kingdonb:main via `f91e346`.
- **108 Rust tests passing**: All 6 crates in `mecris-go-spin/` — unchanged since 2026-04-12.
- **Issue #180 resolved by kingdonb**: `ORDER BY start_time ASC` in walk_inferences query (`a48244d`); Health Connect double-counting fixed in `HealthConnectManager.kt`. Issue still open (bot cannot close kingdonb issues).
- **Rust CI still failing in pr-test.yml**: Pre-existing `working-directory` gap. Tracked in yebyen/mecris#142. Requires `workflow` PAT scope.
- **GDPR data portability gap remains**: No user-data-export endpoint. Only deletion is now covered.

## Verified This Session
- [x] **Upstream sync complete (2026-04-13)**: Fast-forward merge of 7 commits from kingdonb/mecris main. `git rev-list HEAD..upstream/main` = 0.
- [x] **PR #179 merged by kingdonb (2026-04-13)**: Confirmed merged at 02:09 UTC. All bot work from prior sessions is now in kingdonb:main.
- [x] **SMSConsentManager mock fix reviewed (2026-04-13)**: kingdonb commit `1be0021` — removed conflicting `return_value.date.return_value` + `side_effect` from `test_within_window_and_under_limit_can_send`; `return_value` alone is the correct pattern.
- [x] **get_user_preferences reload test added (2026-04-13)**: Commit `1b3cd4f` — `TestOptIn.test_get_user_preferences_reloads_cross_instance` tests the new disk-reload behavior from `a48244d`.
- [x] **yebyen/mecris#165 cross-instance reload test**: Merged by kingdonb via `f91e346`. Issue can be closed — validation criterion met (test in kingdonb:main).
- [x] **NEXT_SESSION.md audited (2026-04-13)**: Previous session. Resolved items marked. NEXT_SESSION.md reflects true state. Plan: yebyen/mecris#166.
- [x] **GDPR right-to-erasure MCP tool (2026-04-13)**: `delete_user_data()` added to `mcp_server.py` (commit `20cfc7b`). 4 unit tests in `tests/test_delete_user_data.py`. FK-safe order: token_bank → users (CASCADE). Syntax validated ✅. Plan: yebyen/mecris#167 (closed).

## Pending Verification (Next Session)
- [ ] **pr-test Python count ≥ 367**: Not yet run for delete_user_data tests (4 new tests + prior 363 = 367 expected). To verify: open PR from yebyen:main → kingdonb:main and dispatch pr-test. yebyen is now 2 commits ahead of kingdonb:main.
- [ ] **Run 004_user_location.sql against live Neon**: `psql $NEON_DB_URL -f scripts/migrations/004_user_location.sql` — adds `location_lat`, `location_lon` columns to live `users` table. Requires kingdonb.
- [ ] **Multi-Tenancy — Android UI Gaps**: Add "log out" button for PocketID auth. Add UI for users to provide phone number, grant/revoke SMS auth, set personal location (lat/lon) for weather heuristics, and select their **Preferred Health Source** (e.g., Google Fit) to prevent double-counting. Tracked in kingdonb/mecris#168.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142: add `working-directory: mecris-go-spin/sync-service` to `Run Rust tests` step in `.github/workflows/pr-test.yml`. Needs `workflow` PAT scope or kingdonb direct action.
- [ ] **send_walk_reminder integration test**: Requires live Spin Cloud deploy with Twilio variables configured.
- [ ] **Twilio Spin variables not yet configured**: `twilio_account_sid`, `twilio_auth_token_encrypted`, `twilio_from_number` — kingdonb must set in Fermyon Cloud.
- [ ] **OpenWeather Spin variables not yet configured**: `openweather_api_key` — global fallback — kingdonb must set in Fermyon Cloud.
- [ ] **Per-user location not yet set in live DB**: Once migration runs, use admin tooling (or manual SQL) to set `location_lat`/`location_lon` for each user in `users` table.
- [ ] **Multiplier Sync Validation**: Verify setting the Review Pump lever in Android updates multiplier in Neon (`SELECT pump_multiplier FROM language_stats`). Requires live device + Neon access.
- [ ] **Ghost Archivist End-to-End**: Run scheduler locally, let archivist job fire, confirm logs show correct reconciliation. (Unit tests complete; E2E still needs live environment.)
- [ ] **kingdonb/mecris#132 verification**: Trigger `/internal/failover-sync` and confirm `daily_completions` is non-zero in Neon if reviews were done.
- [ ] **kingdonb/mecris#127 manual close**: Bot cannot comment/close kingdonb issues (PAT scoped to yebyen only). kingdonb should close #127 as superseded by #132.
- [ ] **Android app has_goal UI**: Confirm Android app picks up `has_goal=false` flag and visually dims untracked languages. Requires live app test.
- [ ] **Majesty Cake Android integration**: `/aggregate-status` backend complete; Android app needs to consume it (kingdonb/mecris#170).
- [ ] **003_multi_tenancy.sql live run**: Run `psql $NEON_DB_URL -f scripts/migrations/003_multi_tenancy.sql` against live Neon.
- [ ] **GDPR-style gap: data portability**: No user-data-export endpoint. See `docs/DATA_ARCHITECTURE_AND_PRIVACY.md`. Right-to-erasure is now implemented (`delete_user_data` MCP tool, commit `20cfc7b`).

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
- **pr-test.yml push constraint**: Bot dispatches pr-test but local commits are not on GitHub until bot workflow ends. Do NOT dispatch pr-test expecting to see local commits — always dispatch AFTER the push (i.e., in the NEXT session after commits land).
- **pr-test.yml sets NEON_DB_URL** (line 93 of pr-test.yml): `postgresql://mecris:mecris@localhost:5432/mecrisdb`. Tests that import mcp_server MUST patch psycopg2.connect or they will try to connect to the real local postgres and hit FK constraints.
- **schema.sql budget_tracking schema**: Fixed in `8597dbe` — columns are now `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE REFERENCES users(pocket_id_sub)`.
- **schema.sql token_bank**: Added in `c88d368` — `CREATE TABLE IF NOT EXISTS token_bank (user_id TEXT PRIMARY KEY REFERENCES users(pocket_id_sub), available_tokens BIGINT NOT NULL DEFAULT 0, monthly_limit BIGINT NOT NULL DEFAULT 1000000, last_refill TIMESTAMPTZ NOT NULL DEFAULT NOW())`.
- **requirements.txt Python dep chain**: `apscheduler>=3.10` + `SQLAlchemy>=2.0` — both needed because `scheduler.py` imports `SQLAlchemyJobStore` from apscheduler.
- **Upstream sync pattern**: `git remote add upstream https://github.com/kingdonb/mecris.git && git fetch upstream main && git merge upstream/main --no-edit`.
- **Rust unit tests**: 6 crates, 108 tests total (sync-service: 64, review-pump: 17, nag-engine-rs: 8, goal-type-rs: 7, review-pump-rs: 6, majesty-cake-rs: 6). All pure functions — `cargo test` runs without Spin host.
- **Rust workspace**: No workspace Cargo.toml in `mecris-go-spin/`. Each crate has `[workspace]` making it self-contained. 6 crates: sync-service, review-pump, nag-engine-rs, goal-type-rs, review-pump-rs, majesty-cake-rs. arabic-skip-counter has no Cargo.toml.
- **Rust workflow fix**: Add `working-directory: mecris-go-spin/sync-service` to `Run Rust tests` step in pr-test.yml. Exact diff in yebyen/mecris#142. Cannot push (no workflow PAT). Additional crates need separate CI steps.
- **target_flow_rate semantics**: This field means "remaining work to reach target" = `(target - daily_completions).max(0)`. When at or above target, value is 0. See `services/review_pump.py:67` and `mecris-go-spin/review-pump/src/lib.rs:114`.
- **Twilio helpers in sync-service**: `build_twilio_url`, `build_twilio_body`, `encode_basic_auth`, `build_sms_request_parts` are pure functions at module scope in `lib.rs`. `send_walk_reminder` is async and requires Spin host to dispatch. `handle_trigger_reminders_post` reads `twilio_account_sid`, `twilio_auth_token_encrypted`, `twilio_from_number` from Spin variables.
- **Phase 3 dispatch loop in sync-service**: `handle_trigger_reminders_post` queries `users` for timezone + location, `walk_inferences` for today's step count, `message_log` for last walk_reminder, evaluates `should_dispatch_reminder(local_hour, step_count, minutes_since_last)` per user. Per-user weather check uses `resolve_lat_lon()` with fallback to global Spin vars. Logs sent reminders to `message_log (type='walk_reminder', channel='sms')`.
- **Per-user location in sync-service**: `resolve_lat_lon(user_lat, user_lon, global_lat, global_lon) -> Option<(f64, f64)>` — pure function, prefers per-user DB columns (`users.location_lat`, `users.location_lon`), falls back to global Spin vars, returns None if no coords. Migration: `scripts/migrations/004_user_location.sql`.
- **Phase 3 heuristics in sync-service**: `is_within_reminder_window(local_hour)`, `is_below_step_threshold(step_count, threshold)`, `is_rate_limit_ok(minutes_since_last: Option<u64>)`, `should_dispatch_reminder(local_hour, step_count, minutes_since_last)` — all pure, all tested. `is_weather_ok_for_walk(weather_main)` — pure, 8 tests. `fetch_weather_main(lat, lon, api_key)` — async, calls OpenWeather Current Weather API.
- **OpenWeather integration in sync-service**: Reads `openweather_api_key` from Spin variable (as global fallback API key). Per-user coordinates from `users.location_lat/location_lon`; global fallback from `openweather_lat/openweather_lon` Spin vars. `https://api.openweathermap.org` in `allowed_outbound_hosts` for sync-service (commit `704f6d4`).
- **Twilio outbound hosts**: `https://api.twilio.com` in `allowed_outbound_hosts` for sync-service (commit `704f6d4`).
- **phone_number_encrypted column**: Exists in `users` table per `scripts/migrations/002_pii_encryption.sql` and `mecris-go-spin/schema.sql`. The trigger-reminders handler queries all users with this column set.
- **message_log table**: Used for rate limiting. Query: `SELECT sent_at::TEXT FROM message_log WHERE user_id = $1 AND type = 'walk_reminder' ORDER BY sent_at DESC LIMIT 1`. Insert after send: `INSERT INTO message_log (user_id, type, channel) VALUES ($1, 'walk_reminder', 'sms')`.
- **--quiet cargo test flag**: Masks unit test output when doc-tests follow with 0 results. Use `cargo test` (without --quiet) to see true per-test output. The `-- --list` flag works correctly.
- **SMSConsentManager datetime mock**: Time-window and daily-limit branches in `can_send_message` use `datetime.now()`. In tests, patch `sms_consent_manager.datetime` and use `mock_dt.now.return_value = datetime(Y, M, D, H, 0, 0)` — `return_value` alone is correct; do NOT also set `side_effect` (it overrides `return_value`). `.date().isoformat()` and `.hour` work naturally on the returned real datetime object.
- **SMSConsentManager get_user_preferences reload**: As of `a48244d` (kingdonb), `get_user_preferences` reloads from disk on every call. `can_send_message` reads `self.consent_data` directly (NOT via `get_user_preferences`) so direct in-memory mutations in tests for daily-limit branch still work correctly.
- **Upstream sync pattern**: `git remote add upstream https://github.com/kingdonb/mecris.git && git fetch upstream main && git merge upstream/main --no-edit`.
- **MCP "Master Mode" security reality**: MCP server has full DB read/write via direct Neon connection. Auth is permissive (reads UUID from local file). Any agent with execution rights on host has full DB access. Documented in `docs/DATA_ARCHITECTURE_AND_PRIVACY.md`.
