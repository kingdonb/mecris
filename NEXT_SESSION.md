# Next Session: Await kingdonb review and merge of kingdonb/mecris#179, then run live migration

## Current Status (2026-04-12)
- **PR #179 open**: kingdonb/mecris#179 opened from yebyen:main — per-user OpenWeather location feature. pr-test: Python ✅ 321 passed Android ✅. Ready for review and merge by kingdonb.
- **yebyen/mecris in sync with kingdonb/mecris**: Both at `ad5ed6c` as base; yebyen is 2 commits ahead with the feature + archive. PR #179 carries those 2 commits.
- **64 Rust tests passing**: `cargo test` in `mecris-go-spin/sync-service/` — all 64 pass, 0 fail.
- **Rust CI still failing in pr-test.yml**: Pre-existing `working-directory` gap. Tracked in yebyen/mecris#142. Requires `workflow` PAT scope — cannot fix from bot.
- **Live migration not yet run**: `scripts/migrations/004_user_location.sql` not yet applied to live Neon DB. Requires kingdonb.

## Verified This Session
- [x] **PR #179 opened (2026-04-12)**: kingdonb/mecris#179 opened from yebyen:main → kingdonb:main. Title: "feat(rust): per-user OpenWeather location from users table". Closes yebyen/mecris#156.
- [x] **pr-test #179 green (2026-04-12)**: Run 24310522452 — Python ✅ 321 passed, 4 skipped; Android ✅. Rust CI pre-existing error (yebyen/mecris#142).
- [x] **PR #178 MERGED (2026-04-12)**: kingdonb/mecris#178 merged by kingdonb. Both repos synced to `ad5ed6c`.
- [x] **Per-user location columns added (2026-04-12)**: `location_lat DOUBLE PRECISION` and `location_lon DOUBLE PRECISION` nullable columns in `mecris-go-spin/schema.sql` and `scripts/migrations/004_user_location.sql`. Commit `132e89e`. Closes yebyen/mecris#156.
- [x] **resolve_lat_lon() implemented and tested**: Pure function — prefers per-user coords, falls back to global Spin vars, returns None if no valid coords. 4 unit tests cover all branches. All 64 tests pass.
- [x] **Dispatch loop refactored**: Weather check moved inside user loop using per-user resolved coordinates. Global Spin vars pre-fetched as fallback. Global pre-loop weather check removed.

## Pending Verification (Next Session)
- [ ] **kingdonb/mecris#179 review and merge**: PR is open and green. Awaiting kingdonb review and merge.
- [ ] **Sync yebyen from upstream after #179 merges**: After merge, run `git fetch upstream main && git merge upstream/main --no-edit` to bring yebyen:main in sync with kingdonb:main.
- [ ] **Run 004_user_location.sql against live Neon**: `psql $NEON_DB_URL -f scripts/migrations/004_user_location.sql` — adds `location_lat`, `location_lon` columns to live `users` table. Requires kingdonb.
- [ ] **Multi-Tenancy — Android UI Gaps**: Add "log out" button for PocketID auth. Add UI for users to provide phone number, grant/revoke SMS auth, and set personal location (lat/lon) for weather heuristics. Tracked in kingdonb/mecris#168.
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
- **Rust unit tests**: Pure functions extracted to module scope — `cargo test` in `mecris-go-spin/sync-service/` runs 64 tests natively without Spin host. Phase 3 weather: `is_weather_ok_for_walk` (8 tests), `resolve_lat_lon` (4 tests in `132e89e`), Phase 3 I/O helpers: `aggregate_step_count` (4), `local_hour_from_timezone` (3), `minutes_since_last_reminder` (4).
- **Rust workspace**: No workspace Cargo.toml in `mecris-go-spin/`. `sync-service` has `[workspace]` making it self-contained (can't join a parent workspace). Each crate must be tested individually. 6 crates, 98 tests total.
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
