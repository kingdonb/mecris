# Next Session: Open PRs to kingdonb/mecris (human-required) or bot-actionable: AI Framework Evaluation (#205) or Local Inference Pipeline (#203)

## Current Status (2026-04-28, post-session #64)
- **narrator context test-implementation skew RESOLVED**: Renamed patch target `_get_presence_status` → `_get_presence_summary` in `test_narrator_aggregate_integration.py`; added `presence_status` top-level key to `get_narrator_context` response in `mcp_server.py`; set `last_human_activity/last_ghost_activity/last_active = None` in `test_mcp_server.py` mock to prevent MagicMock comparison crash. All 7 previously-failing tests now pass. Committed `10be85d`. Closes yebyen/mecris#294.
- **Test suite state**: 860 passed, 9 failed (all remaining failures are `NEON_DB_URL must be set` — pre-existing environment failures requiring a live Neon DB, not fixable in headless CI context).
- **GITHUB_CLASSIC_PAT still expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately (human-required). Blocks all PRs.
- **yebyen/mecris ahead of kingdonb/mecris**: All prior session commits now merged by Kingdon (`04b1059`). New commit `10be85d` (this session) is not yet PRed.
- **Bot-actionable next items**: AI Framework Evaluation (kingdonb/mecris#205, needs Aider) or Local Inference Pipeline (kingdonb/mecris#203, needs Ollama) — both blocked by environment.

## Verified This Session
- [x] **narrator context presence skew (session #64)**: `test_narrator_aggregate_integration.py` patched `mcp_server._get_presence_status` (non-existent); real function is `_get_presence_summary`. `test_mcp_server.py` expected `presence_status` top-level key (missing) and crashed due to MagicMock datetime comparison. Fixed all three issues in 3 files. `PYTHONPATH=. pytest tests/test_narrator_aggregate_integration.py tests/test_mcp_server.py::test_get_narrator_context_includes_presence_status` → **7 passed, 0 failed** (was 7 failures). Commit `10be85d`. **COMPLETE** — closes yebyen/mecris#294.
- [x] **ghost.archivist check_presence skew (session #63)**: Replaced `is_human_present()` call with `check_presence() + is_mecris_cli_active()` composite in `ghost/archivist.py`. Updated YIELD log detail to include `human_present={status.human_present}`. `PYTHONPATH=. pytest tests/test_archivist.py` → **14 passed, 0 failed** (was 0/14 for TestRun). Total verified suite: **194 tests pass** (WASM x4 + archivist + token_bank + pii_encryption + post_mortem). Commit `8f7125d`. **COMPLETE** — closes yebyen/mecris#293.
- [x] **log-message-py WASM component (prior sessions)**: `poc/wasm/log-message-py/app.py` fully implemented with headless import guard. `tests/test_log_message_py_component.py` → **40 passed**. Registered in `mecris-go-spin/sync-service/spin.toml`. Second deliverable (NagNotificationManager.kt Android integration) also complete (commit `ed6692b`). Both deliverables for kingdonb/mecris#213 done.
- [x] **HCAT Sandbox (prior sessions)**: `docker/hcat.Dockerfile` (Alpine SHA-pinned, non-root mecris user) and `scripts/build_hcat.sh` both committed. All deliverables for kingdonb/mecris#210 done.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [x] **URGENT: Refresh GITHUB_CLASSIC_PAT** — returns 401. Bot cannot create PRs to kingdonb/mecris. Renew in GitHub → Settings → Developer Settings → Personal access tokens (classic) with `repo` scope, update the workflow secret `GITHUB_CLASSIC_PAT`.
- [x] **Open PR yebyen:main → kingdonb:main** for session #64 commit (`10be85d`: narrator presence skew fix) and any other pending commits. Closes yebyen/mecris#294.
- [x] **Apply migrate_v8_observability.py to production Neon**: Run `python scripts/migrate_v8_observability.py` in the production environment (with NEON_DB_URL set) to add `last_status`, `last_error`, `intent` columns to `scheduler_election`.
- [x] **Apply secure_variables table to production Neon**: Run `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);` before SecretManager Neon fallback can be used in production.
- [ ] **Cloud Readiness Check**: Monitor Fermyon/Akamai for updates to their Python WASM runtimes. Test a simple SDK v4 "Hello World" to confirm when the platform has caught up.
- [ ] **Align Release Management**: Determine if we should maintain a "Legacy Cloud" branch or implement a compatibility shim until the cloud catch-up is complete.
- [ ] **Verify log-message-py in Cloud**: Once platforms are ready, confirm audit logs appear in cloud KV.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **AI Framework Evaluation (kingdonb/mecris#205)**: Matrix doc and POC script committed (`1a459aa`). Remaining: run `scripts/evaluate_aider.py` in an environment with Aider installed and append results to `docs/AI_FRAMEWORK_EVALUATION.md` evidence log. Requires Aider + an LLM API key.
- [ ] **Budget Governor: WASM Port (kingdonb/mecris#214)**: POC complete and wired into spin.toml. Remaining: Fermyon Cloud variable config — human-required for deployment.
- [ ] **Local Inference Pipeline (kingdonb/mecris#203)**: Integrate Ollama and build a cloud-fallback router.
- [ ] **NEON_DB_URL test failures (9 tests)**: `tests/test_sms_mock.py` (7) and `tests/test_issue_52_template_mapping.py` (2) fail at import time with `OSError: NEON_DB_URL must be set`. These tests don't mock the DB connection at module import — fixing requires patching `psycopg2.connect` or `NEON_DB_URL` at import time in conftest.py or per-test setUp.

## Infrastructure Notes (carried forward)
- **narrator context presence API (post-session #64)**: `get_narrator_context` now returns `presence_status` (string, top-level) alongside `presence` (dict). `_get_presence_summary` (not `_get_presence_status`) is the internal helper. Tests in `test_narrator_aggregate_integration.py` patch `mcp_server._get_presence_summary`.
- **ghost.archivist presence API (post-session #63)**: `check_presence` (returns `PresenceStatus`) and `is_mecris_cli_active` are now both imported in `ghost/archivist.py`. `run()` performs composite check: `status.human_present OR is_mecris_cli_active()`. YIELD log detail: `human_present={status.human_present} age_seconds={status.age_seconds}`. Tests patch `ghost.archivist.check_presence`.
- **WASM component headless test pattern**: `try/except ImportError` around `spin_sdk` imports; stub classes in except block; `if _SPIN_AVAILABLE: incoming_handler = HttpHandler()`. All four WASM component test suites now collect and run without WASM runtime.
- **review-pump-py serialization API (post-session #62)**: `_json_ok(data: dict) -> bytes` → `json.dumps(data).encode()`. `_error_json(message: str) -> bytes` → `json.dumps({"error": message}).encode()`. Both used in `HttpHandler.handle_request`.
- **budget-governor-py pure-logic API (post-session #61)**: `make_bucket_config(limits=None)` → 4-bucket dict with `limit`/`type` keys. `_calc_total_spent(log, bucket)` → all-time sum. `_calc_window_spent(log, bucket)` → 39-min rolling window (handles datetime and ISO string ts; skips invalid). `check_envelope(log, cfg, bucket, cost)` → "allow"/"defer"/"deny"; raises `ValueError("Unknown bucket: ...")`. `recommend_bucket(log, cfg)` → prefers "spend" type, then least-used guard. `get_status(log, cfg, helix_live_balance=None)` → envelope_status/window_minutes/envelope_spend_pct/recommendation/buckets. `budget_gate(log, cfg, bucket, cost=0.01)` → None or dict with budget_halted/envelope/message/routing_recommendation.
- **arabic-skip-counter `_count_reminders`**: Now **synchronous** using `httpx.post` against Neon HTTP SQL API. Derives `https://host/sql` from `postgres://user:pass@host/db`. Returns 0 on any error (fail-safe). `_parse_query_params` guards against None input.
- **`secure_variables` table**: Expected schema: `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);`. SecretManager reads this via `SELECT value FROM secure_variables WHERE key = %s LIMIT 1`. Table does NOT yet exist in production Neon — must be created before the fallback does anything useful.
- **`notification_prefs` write path**: `POST /profile` with `{"notification_prefs": {…}}` writes JSONB to `users.notification_prefs`. Accepts any JSON object; unknown keys are stored and silently ignored on read (falls back to defaults). CORS preflight now includes `PATCH` in `access-control-allow-methods`.
- **`notification_prefs` JSONB keys**: `step_threshold` (u32), `window_start_hour` (u32), `window_end_hour` (u32), `rate_limit_minutes` (u64). All optional; any absent key falls back to default (2000 / 8 / 20 / 240). Empty `{}` or NULL → all defaults.
- **`SecretManager` Neon fallback**: `_neon_connect` kwarg overrides `psycopg2.connect` for test injection. `psycopg2` is lazily imported only when `NEON_DB_URL` is set AND no injected connect. `HEADLESS_LOOPBACK_KEYS = ["GEMINI_API_KEY"]` is the canonical list.
- **`HeadlessLoopback._SYSTEM_PASSTHROUGH`**: `frozenset({"PATH", "HOME", "TERM", "USER", "SHELL", "LANG", "LC_ALL"})` — always forwarded to subprocess. No credentials in this set.
- **`write_obs_status` signature (Rust)**: `(connection: &Connection, user_id: &str, role: &str, last_status: &str, intent: &str, last_error: Option<&str>)`. Uses `ParameterValue::DbNull` for `None` last_error. Fail-safe: on UPDATE error, logs `[DEBUG] write_obs_status: UPDATE failed (columns may be absent): ...` and returns silently.
- **`cloud_role()` extracted**: Reads `cloud_provider` Spin variable; maps "akamai" → "akamai_functions", "fermyon" → "fermyon_cloud", else "unknown_cloud". Used by both `register_cloud_heartbeat` and `write_obs_status` call sites.
- **`obs_status_query()` pure helper**: Returns the static SQL UPDATE string. Used in `write_obs_status`; tested independently without a DB connection.
- **`_write_obs_status` signature (Python)**: `(self, cur, last_status: str, intent: str, error: str = None)`. The UPDATE sets all three obs fields; omitting `error` writes NULL (clears stale errors). SAVEPOINT mechanism unchanged.
- **Observability columns are fail-safe**: `_write_obs_status()` in `scheduler.py` uses a SAVEPOINT per write; if columns are absent, rolls back the savepoint, sets `_has_obs_columns = False` (cached), and logs at DEBUG. Pre-migration environments are fully safe.
- **HealthChecker is backward-compatible**: Column check via `information_schema.columns`; if obs columns absent, returns `last_status/last_error/intent = None` for every process dict. No schema changes needed at read time.
- **related_bookmarks is fail-open**: If `_enrich_bookmarks_for_narrator` raises for any reason, `get_narrator_context` catches the exception, logs a warning, and returns `related_bookmarks: []`. Safe to call anywhere.
- **TF-IDF index rebuilt each call**: `_enrich_bookmarks_for_narrator` loads bookmarks and builds a fresh `BookmarkIndex` on every `get_narrator_context` call. Acceptable for small files; if performance becomes an issue, consider a module-level cached index.
- **GITHUB_CLASSIC_PAT is expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately.
- **CopilotLoopback command**: `["gh", "copilot", "--", "-p", full_prompt]` — `--` prevents `gh` from consuming `-p`; passes prompt as arg not stdin. `GH_COPILOT_BASE = ["gh", "copilot", "--"]`.
- **CopilotLoopback default timeout**: 120s (vs HeadlessLoopback's 1800s for gemini). Import from `ghost.copilot_loopback`.
- **Universal Clean Build Strategy**: `find . -name '.venv*' -type d -exec rm -rf {} + && find . -name '__pycache__' -type d -exec rm -rf {} + && uv venv .venv_build --clear --python 3.13 && . .venv_build/bin/activate && uv pip install componentize-py==0.23.0 spin-sdk==4.0.0 && componentize-py -w spin:up/http-trigger@4.0.0 componentize -p . -p .venv_build/lib/python3.13/site-packages app -o component.wasm`
- **SDK v4 async mandate**: `variables.get`, `kv.open_default`, `store.get`, `postgres.query`, and `http.send` are all **async** in SDK 4.0.0.
- **Observant Presence logic**: `is_human_present` checks `/tmp/mecris_presence.lock` and `pgrep -f cli.main`. Logs but does not block registration in `MecrisScheduler`.
- **HCAT sandbox image**: `docker/hcat.Dockerfile` updated with `python3-modules` for stdlib completeness.
- **calculateGoalMet**: `goalMetFromServer || (targetFlowRate != null && targetFlowRate <= 0.0)`. Used in `ReviewPumpWidget`.
- **PLAY MODE threshold**: `outstandingDebt > targetFlowRate * 7` — more than one week of daily work remaining.
- **BECKON threshold**: `outstandingDebt >= 300` — signals user should consider a new Beeminder reviewstack goal.
- **outstanding_debt in LanguageStatDto**: Field added as `Int?` with default `null`. Falls back to `stat.current` when absent. Backend `/languages` API does NOT yet return this field.
- **log-message-py component API**: `POST /internal/log-message` with `{"type": str, "channel": str, "sent_at": ISO|optional}`.
- **MECRIS_MODE=standalone** bypasses JWKS; `MECRIS_MODE=cloud` enforces RSA verification.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning.
- **poc/wasm/ pattern**: Use `importlib.util.spec_from_file_location("unique_name", path)` when loading WASM component `app.py` files in tests to avoid `sys.modules['app']` collision.
- **rag_generator model**: `claude-haiku-4-5-20251001` by default.
- **Apply migrate_v7 to production Neon**: `token_bank` and `autonomous_turns` tables. Run `python scripts/migrate_v7_autonomous_tracking.py`.
- **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.
- **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- **Verify ask_mecris answer quality**: With a real `ANTHROPIC_API_KEY` in the MCP server env, call `ask_mecris("what is mecris?")` and confirm the `answer` field is prose (not None).
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **Note on Cloud Cron**: The Spin Cron trigger is currently **DISABLED** in `spin.toml` to prevent it from masking local framework issues. Do not re-enable until the MCP leader can coordinate these events.
til the MCP leader can coordinate these events.
al `ANTHROPIC_API_KEY` in the MCP server env, call `ask_mecris("what is mecris?")` and confirm the `answer` field is prose (not None).
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **Note on Cloud Cron**: The Spin Cron trigger is currently **DISABLED** in `spin.toml` to prevent it from masking local framework issues. Do not re-enable until the MCP leader can coordinate these events.
