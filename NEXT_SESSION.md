# Next Session: Open PRs to kingdonb/mecris (human-required) or CI/CD pipeline for legacy-cloud branch

## Current Status (2026-04-28, post-session #66)
- **legacy-cloud branch created**: yebyen/mecris `legacy-cloud` branch (commit `51a5fc2`) contains all 4 WASM components reverted from SDK v4 (async) to SDK v3 (sync). Implements step 3 of `docs/SPIN_V3_COMPATIBILITY_PLAN.md`.
- **Upstream synced**: Merged 3 commits from kingdonb/mecris main (`17d4855` test fix, `95c3564` NEXT_SESSION.md update, `0303d29` Spin V3 compat plan). yebyen/mecris main is now ahead with these + the archive commit.
- **Test suite state**: 860 passed, 0 failed (all NEON_DB_URL failures resolved in session #65). 151 WASM component headless tests pass.
- **GITHUB_CLASSIC_PAT still expired**: Bot cannot create PRs to kingdonb/mecris. Human must renew.
- **CI/CD for legacy-cloud**: Step 4 of SPIN_V3_COMPATIBILITY_PLAN.md (GitHub Actions deployment from legacy-cloud) is human-required.

## Verified This Session
- [x] **Upstream sync (session #66)**: Merged 3 kingdonb/mecris commits (`17d4855`, `95c3564`, `0303d29`) into yebyen/mecris main. No conflicts. Merge commit `f967f2b`. **COMPLETE**.
- [x] **legacy-cloud branch (session #66)**: Created `legacy-cloud` from yebyen/mecris main. Reverted all 4 WASM components to sync API. Pushed to yebyen/mecris via MCP. `PYTHONPATH=. python3 -m pytest tests/test_*_component.py` → **151 passed, 0 failed**. Commit `51a5fc2`. Closes yebyen/mecris#296. **COMPLETE**.
- [x] **NEON_DB_URL test failures (session #65)**: `tests/conftest.py` `mock_usage_tracker_init` autouse fixture added. Root cause: `smart_send_message()` unconditionally calls `get_tracker()` → `UsageTracker()` → `init_database()` raises `EnvironmentError` when `NEON_DB_URL` absent. Fix: mock `init_database` to no-op and reset singleton per test. **COMPLETE** — closes yebyen/mecris#295.
- [x] **narrator context presence skew (session #64)**: `test_narrator_aggregate_integration.py` patched `mcp_server._get_presence_status` (non-existent); real function is `_get_presence_summary`. Fixed all three issues in 3 files. **COMPLETE** — closes yebyen/mecris#294.
- [x] **ghost.archivist check_presence skew (session #63)**: Replaced `is_human_present()` call with `check_presence() + is_mecris_cli_active()` composite in `ghost/archivist.py`. **COMPLETE** — closes yebyen/mecris#293.
- [x] **log-message-py WASM component (prior sessions)**: `poc/wasm/log-message-py/app.py` fully implemented with headless import guard. Both deliverables for kingdonb/mecris#213 done.
- [x] **HCAT Sandbox (prior sessions)**: `docker/hcat.Dockerfile` and `scripts/build_hcat.sh` both committed. All deliverables for kingdonb/mecris#210 done.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **URGENT: Refresh GITHUB_CLASSIC_PAT** — returns 401. Bot cannot create PRs to kingdonb/mecris. Renew in GitHub → Settings → Developer Settings → Personal access tokens (classic) with `repo` scope, update the workflow secret `GITHUB_CLASSIC_PAT`.
- [ ] **Open PR yebyen:main → kingdonb:main** for all pending commits from sessions #64–#66 (narrator presence fix, NEON_DB_URL fix, upstream merge + legacy-cloud setup). Closes yebyen/mecris#294, #295, #296.
- [ ] **CI/CD Pipeline for legacy-cloud (step 4)**: Update GitHub Actions deployment workflows to trigger Fermyon/Akamai deployments only from the `legacy-cloud` branch. `main` continues to deploy to local Kubernetes `spin-tainer`. Ref: `docs/SPIN_V3_COMPATIBILITY_PLAN.md` step 4.
- [ ] **Cloud Readiness Check**: Monitor Fermyon/Akamai for updates to their Python WASM runtimes. Test a simple SDK v4 "Hello World" to confirm when the platform has caught up.
- [ ] **Apply migrate_v8_observability.py to production Neon**: Run `python scripts/migrate_v8_observability.py` in the production environment (with NEON_DB_URL set) to add `last_status`, `last_error`, `intent` columns to `scheduler_election`.
- [ ] **Apply secure_variables table to production Neon**: Run `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);` before SecretManager Neon fallback can be used in production.
- [ ] **Verify log-message-py in Cloud**: Once platforms are ready, confirm audit logs appear in cloud KV.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **AI Framework Evaluation (kingdonb/mecris#205)**: Matrix doc and POC script committed (`1a459aa`). Remaining: run `scripts/evaluate_aider.py` in an environment with Aider installed and append results to `docs/AI_FRAMEWORK_EVALUATION.md` evidence log. Requires Aider + an LLM API key.
- [ ] **Budget Governor: WASM Port (kingdonb/mecris#214)**: POC complete and wired into spin.toml. Remaining: Fermyon Cloud variable config — human-required for deployment.
- [ ] **Local Inference Pipeline (kingdonb/mecris#203)**: Integrate Ollama and build a cloud-fallback router.
- [ ] **Backporting workflow (legacy-cloud step 5)**: As bugs are fixed in main leading up to v0.0.1, cherry-pick to `legacy-cloud`. WASM component changes need manual async→sync adjustment during cherry-pick.

## Infrastructure Notes (carried forward)
- **legacy-cloud WASM sync API (post-session #66)**: All 4 WASM components on `legacy-cloud` branch use sync `def handle_request` (SDK v3). Specific changes: `arabic-skip-counter`: `_spin_variables.get("neon_db_url")` (no await). `log-message-py`: `kv.open_default()`, `store.get()`, `store.set()` (no await). `budget-governor-py`: `_get_bucket_config_from_spin_vars()` and `_fetch_helix_balance_spin()` are sync; `variables.get()`, `kv.open_default()`, `store.get()`, `store.set()` (no await). `review-pump-py`: `def handle_request` only (no KV/vars calls). Build target for legacy-cloud: `componentize-py==0.13.0 spin-sdk==3.0.0`, `componentize-py -w spin:http-trigger@0.2.0`.
- **conftest.py mock_usage_tracker_init (post-session #65)**: `@pytest.fixture(autouse=True)` in `tests/conftest.py`. When `NEON_DB_URL` absent: resets `usage_tracker._tracker_instance = None` and patches `UsageTracker.init_database = lambda self: None` via monkeypatch. Prevents `get_tracker()` from raising. Tests needing `get_user_preferences` return values still patch that method themselves. Fixture is conditional on `NEON_DB_URL` absence — does NOT interfere when real Neon is present.
- **narrator context presence API (post-session #64)**: `get_narrator_context` now returns `presence_status` (string, top-level) alongside `presence` (dict). `_get_presence_summary` (not `_get_presence_status`) is the internal helper. Tests in `test_narrator_aggregate_integration.py` patch `mcp_server._get_presence_summary`.
- **ghost.archivist presence API (post-session #63)**: `check_presence` (returns `PresenceStatus`) and `is_mecris_cli_active` are now both imported in `ghost/archivist.py`. `run()` performs composite check: `status.human_present OR is_mecris_cli_active()`. YIELD log detail: `human_present={status.human_present} age_seconds={status.age_seconds}`. Tests patch `ghost.archivist.check_presence`.
- **WASM component headless test pattern**: `try/except ImportError` around `spin_sdk` imports; stub classes in except block; `if _SPIN_AVAILABLE: incoming_handler = HttpHandler()`. All four WASM component test suites now collect and run without WASM runtime.
- **review-pump-py serialization API (post-session #62)**: `_json_ok(data: dict) -> bytes` → `json.dumps(data).encode()`. `_error_json(message: str) -> bytes` → `json.dumps({"error": message}).encode()`. Both used in `HttpHandler.handle_request`.
- **budget-governor-py pure-logic API (post-session #61)**: `make_bucket_config(limits=None)` → 4-bucket dict with `limit`/`type` keys. `_calc_total_spent(log, bucket)` → all-time sum. `_calc_window_spent(log, bucket)` → 39-min rolling window. `check_envelope(log, cfg, bucket, cost)` → "allow"/"defer"/"deny". `recommend_bucket(log, cfg)` → prefers "spend" type, then least-used guard. `get_status(log, cfg, helix_live_balance=None)` → full status report. `budget_gate(log, cfg, bucket, cost=0.01)` → None or dict with budget_halted/envelope/message/routing_recommendation.
- **arabic-skip-counter `_count_reminders`**: Now **synchronous** using `httpx.post` against Neon HTTP SQL API. Derives `https://host/sql` from `postgres://user:pass@host/db`. Returns 0 on any error (fail-safe). `_parse_query_params` guards against None input.
- **`secure_variables` table**: Expected schema: `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);`. SecretManager reads this via `SELECT value FROM secure_variables WHERE key = %s LIMIT 1`. Table does NOT yet exist in production Neon.
- **`SecretManager` Neon fallback**: `_neon_connect` kwarg overrides `psycopg2.connect` for test injection. `psycopg2` is lazily imported only when `NEON_DB_URL` is set AND no injected connect. `HEADLESS_LOOPBACK_KEYS = ["GEMINI_API_KEY"]` is the canonical list.
- **`HeadlessLoopback._SYSTEM_PASSTHROUGH`**: `frozenset({"PATH", "HOME", "TERM", "USER", "SHELL", "LANG", "LC_ALL"})` — always forwarded to subprocess. No credentials in this set.
- **`write_obs_status` signature (Rust)**: `(connection: &Connection, user_id: &str, role: &str, last_status: &str, intent: &str, last_error: Option<&str>)`. Fail-safe on UPDATE error.
- **`cloud_role()` extracted**: Reads `cloud_provider` Spin variable; maps "akamai" → "akamai_functions", "fermyon" → "fermyon_cloud", else "unknown_cloud".
- **Observability columns are fail-safe**: `_write_obs_status()` in `scheduler.py` uses a SAVEPOINT per write; if columns are absent, rolls back the savepoint, sets `_has_obs_columns = False` (cached), and logs at DEBUG.
- **HealthChecker is backward-compatible**: Column check via `information_schema.columns`; if obs columns absent, returns `last_status/last_error/intent = None` for every process dict.
- **related_bookmarks is fail-open**: If `_enrich_bookmarks_for_narrator` raises for any reason, `get_narrator_context` catches the exception, logs a warning, and returns `related_bookmarks: []`.
- **GITHUB_CLASSIC_PAT is expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately.
- **CopilotLoopback command**: `["gh", "copilot", "--", "-p", full_prompt]` — `--` prevents `gh` from consuming `-p`. `GH_COPILOT_BASE = ["gh", "copilot", "--"]`. Default timeout: 120s.
- **SDK v4 async mandate (main branch)**: `variables.get`, `kv.open_default`, `store.get`, `postgres.query`, and `http.send` are all **async** in SDK 4.0.0 on main. legacy-cloud uses sync equivalents.
- **rag_generator model**: `claude-haiku-4-5-20251001` by default.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning.
- **poc/wasm/ pattern**: Use `importlib.util.spec_from_file_location("unique_name", path)` when loading WASM component `app.py` files in tests to avoid `sys.modules['app']` collision.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **Note on Cloud Cron**: The Spin Cron trigger is currently **DISABLED** in `spin.toml` to prevent it from masking local framework issues. Do not re-enable until the MCP leader can coordinate these events.
