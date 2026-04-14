# Next Session: Open PR for Twilio Phase 2 wiring; run pr-test to confirm 91 Rust tests green

## Current Status (2026-04-14)
- **Twilio webhook Phase 2 wiring complete** (commit `db9c8fa`, yebyen/mecris#178): `handle_twilio_webhook_post` now decrypts `phone_number_encrypted` per user, matches against Twilio `From`, pushes Beeminder datapoint, and inserts `message_log (type='walk_ack', channel='sms')`. 91 Rust tests pass (was 82; +9 for `normalize_phone`/`phones_match` helpers).
- **yebyen/mecris is 2 commits ahead of kingdonb:main**: `9bdf4e75` (synced from upstream this session) + `db9c8fa` (Phase 2 wiring). Bot workflow will push at end of this run.
- **PR #182 (or new) must be opened next session**: the push hasn't landed yet — PR creation requires commit to be visible on GitHub.
- **kingdonb commit `9bdf4e75`** (Groq-Beeminder sync) is now in yebyen:main (synced this session).

## Verified This Session
- [x] **Upstream sync**: pulled `9bdf4e75` (Groq-Beeminder sync, feat: Groq odometer + Beeminder integration) from kingdonb. Fast-forward merge succeeded.
- [x] **Twilio Phase 2 wiring** (commit `db9c8fa`): `handle_twilio_webhook_post` replaces TODO block — DB user-lookup loop, `phones_match()` comparison, `push_to_beeminder()` call, `message_log` insert. 91 Rust tests pass.
- [x] **PR #181 confirmed merged**: kingdonb merged `yebyen:main → kingdonb:main` at 14:13 UTC today.

## Pending Verification (Next Session)
- [ ] **Verify commit `db9c8fa` pushed**: check `git log --oneline -2` on yebyen/mecris after workflow ends.
- [ ] **Open new PR (yebyen:main → kingdonb:main)**: one commit `db9c8fa` — Twilio Phase 2 wiring. PR description: references kingdonb/mecris#140, mentions 91 Rust tests.
- [ ] **Run pr-test on new PR**: dispatch pr-test once PR is open. Expect 91 Rust tests + ≥377 Python tests green.
- [ ] **Run 004_user_location.sql against live Neon**: `psql $NEON_DB_URL -f scripts/migrations/004_user_location.sql` — adds `location_lat`, `location_lon` columns to live `users` table. Requires kingdonb.
- [ ] **Twilio webhook Phase 2 live E2E**: requires Twilio Spin variables in Fermyon Cloud (`twilio_account_sid`, `twilio_auth_token_encrypted`, `twilio_from_number`) — set by kingdonb.
- [ ] **Multi-Tenancy — Android UI Gaps**: Add "log out" button for PocketID auth. Add UI for users to provide phone number, grant/revoke SMS auth, set personal location (lat/lon) for weather heuristics, and select their **Preferred Health Source** (e.g., Google Fit) to prevent double-counting. Tracked in kingdonb/mecris#168.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142: add `working-directory: mecris-go-spin/sync-service` to `Run Rust tests` step in `.github/workflows/pr-test.yml`. Needs `workflow` PAT scope or kingdonb direct action.
- [ ] **send_walk_reminder integration test**: Requires live Spin Cloud deploy with Twilio variables configured.
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
- **Fine-grained PAT**: `GITHUB_TOKEN` is scoped to yebyen/mecris only — cannot comment or close issues on kingdonb/mecris. Cannot create PRs on kingdonb/mecris either — use `GITHUB_CLASSIC_PAT` via `gh` CLI.
- **pr-test.yml push constraint**: Bot dispatches pr-test but local commits are not on GitHub until bot workflow ends. Do NOT dispatch pr-test expecting to see local commits — always dispatch AFTER the push (i.e., in the NEXT session after commits land).
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main resolves this automatically.
- **psycopg2 not installed in CI runner**: `test_presence_neon.py` may have pre-existing failures — not a regression.
- **Python venv not present in bot runner**: `PYTHONPATH=. .venv/bin/pytest` cannot run in bot context; Python tests validated via kingdonb/mecris pr-test workflow instead.
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, ...)` + `patch("psycopg2.connect")` before importing. See `_make_mcp_importable()` in `test_mcp_server.py`, `test_cloud_sync.py`, `test_standalone_access.py`, `test_unauthorized_access.py`, `test_walk_sync.py`.
- **SQL mock matching pitfall**: `"DELETE" in sql` matches `ON DELETE CASCADE` in CREATE TABLE strings. Use `"DELETE FROM <table>" in sql` for precise assertions. See test_delete_user_data.py commit `5f25fa9`.
- **delete_user_data import note**: `UsageTracker()` runs at module import time (mcp_server.py:249). Tests must import with NEON_DB_URL set; test the no-URL case by clearing env var at call time (after import), not before.
- **export_user_data cursor pattern**: `_rows(cur, table, col)` helper uses `cur.description` for column names and returns list of dicts. Mock `cursor.description` as `[("pocket_id_sub",)]` and `fetchall.side_effect` as `[[user_row]] + [[]]*5` for happy-path tests. ALSO mock `cursor.fetchone.return_value = None` to prevent `UsageTracker.resolve_user_id` from returning a MagicMock via the familiar_id lookup branch.
- **UsageTracker.resolve_user_id DB call pitfall**: When NEON_DB_URL is set (even fake), `resolve_user_id(non_None_user_id)` calls `psycopg2.connect → cursor.execute → cursor.fetchone()`. If `fetchone` is not mocked, it returns a truthy MagicMock and `row[0]` becomes `target_user_id`. Always set `mock_cur.fetchone.return_value = None` in cursor mocks for export_user_data tests.
- **standalone test safety**: `_record_presence` (mcp_server.py:46-54) is fully guarded — returns None if no store, wraps upsert in try/except. Main handler (mcp_server.py:367-490) has outer try/except that returns dict on failure. `/narrator/context` always returns HTTP 200 in standalone mode.
- **Ghost Archivist lazy-import pattern**: `BeeminderClient` and `LanguageSyncService` are imported INSIDE `perform_archival_sync()` function body. Patch at source modules, not at `ghost.archivist_logic`.
- **cloud-sync patch pattern**: `language_sync_service` is a module-level variable. Use `patch("mcp_server.language_sync_service")` AFTER importing mcp_server within env+psycopg2 patches.
- **BeeminderClient note**: `UsageTracker.__init__` requires `NEON_DB_URL` even in the no-DB fallback path — mock UsageTracker when testing the env-var-only path.
- **Multi-tenancy schema**: `language_stats` PK is `(user_id, language_name)`; `budget_tracking` has `user_id UNIQUE` with FK to `users(pocket_id_sub)`. All queries scope by user_id.
- **schema.sql budget_tracking schema**: Fixed in `8597dbe` — columns are now `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE REFERENCES users(pocket_id_sub)`.
- **schema.sql token_bank**: Added in `c88d368` — `CREATE TABLE IF NOT EXISTS token_bank (user_id TEXT PRIMARY KEY REFERENCES users(pocket_id_sub), available_tokens BIGINT NOT NULL DEFAULT 0, monthly_limit BIGINT NOT NULL DEFAULT 1000000, last_refill TIMESTAMPTZ NOT NULL DEFAULT NOW())`.
- **requirements.txt Python dep chain**: `apscheduler>=3.10` + `SQLAlchemy>=2.0` — both needed because `scheduler.py` imports `SQLAlchemyJobStore` from apscheduler.
- **Upstream sync pattern**: `git remote add upstream https://github.com/kingdonb/mecris.git && git fetch upstream main && git merge upstream/main --no-edit`.
- **Rust unit tests**: 91 tests in sync-service (as of `db9c8fa`). All pure functions — `cargo test` runs without Spin host.
- **Rust workspace**: No workspace Cargo.toml in `mecris-go-spin/`. Each crate has `[workspace]` making it self-contained. 6 crates: sync-service, review-pump, nag-engine-rs, goal-type-rs, review-pump-rs, majesty-cake-rs. arabic-skip-counter has no Cargo.toml.
- **Rust workflow fix**: Add `working-directory: mecris-go-spin/sync-service` to `Run Rust tests` step in pr-test.yml. Exact diff in yebyen/mecris#142. Cannot push (no workflow PAT). Additional crates need separate CI steps.
- **target_flow_rate semantics**: This field means "remaining work to reach target" = `(target - daily_completions).max(0)`. When at or above target, value is 0. See `services/review_pump.py:67` and `mecris-go-spin/review-pump/src/lib.rs:114`.
- **Twilio helpers in sync-service**: `build_twilio_url`, `build_twilio_body`, `encode_basic_auth`, `build_sms_request_parts` are pure functions at module scope in `lib.rs`. `send_walk_reminder` is async and requires Spin host to dispatch. `handle_trigger_reminders_post` reads `twilio_account_sid`, `twilio_auth_token_encrypted`, `twilio_from_number` from Spin variables.
- **Twilio inbound webhook Phase 2 complete**: `handle_twilio_webhook_post` validates sig (403 on fail), on affirmative: queries all users with `phone_number_encrypted`, decrypts each, matches against `From` via `phones_match()`, calls `push_to_beeminder(beeminder_goal, 1.0)`, inserts `message_log (type='walk_ack', channel='sms')`. `normalize_phone()` strips formatting for E.164 comparison. Graceful degradation if `db_url` not configured.
- **Phase 3 dispatch loop in sync-service**: `handle_trigger_reminders_post` queries `users` for timezone + location, `walk_inferences` for today's step count, `message_log` for last walk_reminder, evaluates `should_dispatch_reminder(local_hour, step_count, minutes_since_last)` per user. Per-user weather check uses `resolve_lat_lon()` with fallback to global Spin vars. Logs sent reminders to `message_log (type='walk_reminder', channel='sms')`.
- **Per-user location in sync-service**: `resolve_lat_lon(user_lat, user_lon, global_lat, global_lon) -> Option<(f64, f64)>` — pure function, prefers per-user DB columns (`users.location_lat`, `users.location_lon`), falls back to global Spin vars, returns None if no coords. Migration: `scripts/migrations/004_user_location.sql`.
- **Phase 3 heuristics in sync-service**: `is_within_reminder_window(local_hour)`, `is_below_step_threshold(step_count, threshold)`, `is_rate_limit_ok(minutes_since_last: Option<u64>)`, `should_dispatch_reminder(local_hour, step_count, minutes_since_last)` — all pure, all tested. `is_weather_ok_for_walk(weather_main)` — pure, 8 tests. `fetch_weather_main(lat, lon, api_key)` — async, calls OpenWeather Current Weather API.
- **OpenWeather integration in sync-service**: Reads `openweather_api_key` from Spin variable (as global fallback API key). Per-user coordinates from `users.location_lat/location_lon`; global fallback from `openweather_lat/openweather_lon` Spin vars. `https://api.openweathermap.org` in `allowed_outbound_hosts` for sync-service (commit `704f6d4`).
- **Twilio outbound hosts**: `https://api.twilio.com` in `allowed_outbound_hosts` for sync-service (commit `704f6d4`).
- **phone_number_encrypted column**: Exists in `users` table per `scripts/migrations/002_pii_encryption.sql` and `mecris-go-spin/schema.sql`. The trigger-reminders handler queries all users with this column set. The inbound webhook handler now decrypts each user's phone to match against the From number.
- **message_log table**: Used for rate limiting. Query: `SELECT sent_at::TEXT FROM message_log WHERE user_id = $1 AND type = 'walk_reminder' ORDER BY sent_at DESC LIMIT 1`. Insert after send: `INSERT INTO message_log (user_id, type, channel) VALUES ($1, 'walk_reminder', 'sms')`. For walk acks: use `type='walk_ack'` (now implemented in handle_twilio_webhook_post).
- **--quiet cargo test flag**: Masks unit test output when doc-tests follow with 0 results. Use `cargo test` (without --quiet) to see true per-test output. The `-- --list` flag works correctly.
- **SMSConsentManager datetime mock**: Time-window and daily-limit branches in `can_send_message` use `datetime.now()`. In tests, patch `sms_consent_manager.datetime` and use `mock_dt.now.return_value = datetime(Y, M, D, H, 0, 0)` — `return_value` alone is correct; do NOT also set `side_effect` (it overrides `return_value`). `.date().isoformat()` and `.hour` work naturally on the returned real datetime object.
- **SMSConsentManager get_user_preferences reload**: As of `a48244d` (kingdonb), `get_user_preferences` reloads from disk on every call. `can_send_message` reads `self.consent_data` directly (NOT via `get_user_preferences`) so direct in-memory mutations in tests for daily-limit branch still work correctly.
- **MCP "Master Mode" security reality**: MCP server has full DB read/write via direct Neon connection. Auth is permissive (reads UUID from local file). Any agent with execution rights on host has full DB access. Documented in `docs/DATA_ARCHITECTURE_AND_PRIVACY.md`.
- **kingdonb/mecris#180 already fixed**: ORDER BY and Health Connect deduplication were resolved in commits `a48244d`/`404fdec` (both in kingdonb:main and yebyen:main). Issue still open on kingdonb/mecris — bot cannot close it.
