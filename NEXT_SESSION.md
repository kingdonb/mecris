# Next Session: Test coverage for scheduler.py

## Current Status (2026-04-30, post-session #79)
- **claude_api_budget_scraper.py test coverage (session #79)**: 24 new tests in `tests/test_claude_api_budget_scraper.py` — CreditBalance (4), ClaudeConsoleScraper init (3), _load_cached_balance (4), _save_cached_balance (2), _scaffold_scraper (2), _playwright_implementation (1), get_credit_balance (3), set_manual_balance (3), convenience functions (2). All 24 passed in 0.32s. Commit `594b309`. Closes yebyen/mecris#313.
- **mcp_reconcile_budget.py test coverage (session #78)**: 18 new tests in `tests/test_mcp_reconcile_budget.py` — get_current_budget_status (3), record_reconciliation (3), update_budget_directly (4), get_reconciliation_status (2), main() CLI paths (6). All 18 passed. Commit `2c19849`. Closes yebyen/mecris#312.
- **Test suite state**: 24 new tests for claude_api_budget_scraper.py added. CI bare-env failures in test_scheduler_election and test_sms_mock are pre-existing and unrelated.
- **GITHUB_CLASSIC_PAT still expired**: Bot cannot create PRs to kingdonb/mecris. Human must renew.
- **Upstream sync**: yebyen/mecris is ahead of kingdonb/mecris by many sessions; history has diverged since session #66. Future syncs must cherry-pick new files only.
- **Next bot priority**: Test coverage for `scheduler.py` (484 lines — only election logic tested in test_scheduler_election.py). Or: AI Framework Evaluation (kingdonb/mecris#205).

## Verified This Session
- [x] **claude_api_budget_scraper.py test coverage (session #79)**: `tests/test_claude_api_budget_scraper.py` — 24 tests (CreditBalance×4, ClaudeConsoleScraper init×3, _load_cached_balance×4, _save_cached_balance×2, _scaffold_scraper×2, _playwright_implementation×1, get_credit_balance×3, set_manual_balance×3, convenience functions×2). `PYTHONPATH=. python3 -m pytest tests/test_claude_api_budget_scraper.py -v` → 24 passed in 0.32s. Commit `594b309`. Closes yebyen/mecris#313. **COMPLETE**.
- [x] **mcp_reconcile_budget.py test coverage (session #78)**: `tests/test_mcp_reconcile_budget.py` — 18 tests (get_current_budget_status×3, record_reconciliation×3, update_budget_directly×4, get_reconciliation_status×2, main×6). `PYTHONPATH=. python3 -m pytest tests/test_mcp_reconcile_budget.py -v` → 18 passed in 0.33s. Commit `2c19849`. Closes yebyen/mecris#312. **COMPLETE**.
- [x] **legacy-cloud playwright backport (session #77)**: `git log origin/legacy-cloud | head -1` → `2beb598 fix(imports): make playwright import lazy in fetch_groq_usage.py`. `python3 -c "import fetch_groq_usage"` → OK. Commit `2beb598` on `origin/legacy-cloud`. Closes yebyen/mecris#310. **COMPLETE**.
- [x] **groq_odometer_tracker.py test coverage (session #77)**: `tests/test_groq_odometer_tracker.py` — 24 tests (OdometerStatus×3, OdometerReading×3, _calculate_daily_usage×3, _days_until_month_end×4, check_reminder_needs×5, get_usage_for_virtual_budget×3, generate_narrator_context×3). `PYTHONPATH=. python3 -m pytest tests/test_groq_odometer_tracker.py -v` → 24 passed. Commit `c60c78a`. Closes yebyen/mecris#311. **COMPLETE**.
- [x] **billing_reconciliation.get_reconciliation_summary tests (session #76)**: 6 new tests — RealDictCursor happy path, empty results, multiple-provider avg, no neon_url raises, DB exception reraises, user_id override. Suite: **41 passed** for billing_reconciliation.py. Commit `7a69b2d`. Closes yebyen/mecris#309.
- [x] **claude_monitor.py async path tests (session #75)**: `tests/test_claude_monitor.py` now has 41 tests (27 existing + 14 new). TestHealthCheck (4): no_api_key→not_configured, api_key+usage→ok, api_key+no_usage→error, exception→error. TestRecordUsage (10): happy path, get_current_usage=None, save failure, credits_remaining/used updated, description stored, >30d pruned, recent entries kept, alerts on success, no alerts on failure, exception→False. `PYTHONPATH=. pytest tests/test_claude_monitor.py -v` → 41 passed. Commit `721bfd1`. Closes yebyen/mecris#308. **COMPLETE**.
- [x] **billing_reconciliation.py test coverage (session #74)**: `tests/test_billing_reconciliation.py` (35 tests). `PYTHONPATH=. python3 -m pytest tests/test_billing_reconciliation.py -v` → 35 passed. Commit `d41a848`. Closes yebyen/mecris#307. **COMPLETE**.
- [x] **claude_monitor.py test coverage (session #73)**: `tests/test_claude_monitor.py` (27 tests). Twilio stubbed via `sys.modules` at import time. Commit `d4b9403`. Closes yebyen/mecris#306. **COMPLETE**.
- [x] **RAG test coverage (session #72)**: `tests/test_rag_retriever.py` (46 tests) + `tests/test_rag_generator.py` (15 tests). Total suite: 941 passed, 7 skipped. Commit `bc27e78`. Closes yebyen/mecris#305. **COMPLETE**.
- [x] **test_narrator_context.py async fix (session #71)**: 6 async tests rewritten as plain pytest classes with mocked httpx. Commit `b9f1bbb`. Closes yebyen/mecris#303. **COMPLETE**.
- [x] **utcnow() deprecation fix (session #70)**: `datetime.utcnow()` → `datetime.now(timezone.utc)` in 8 files. 880 passed, 0 failed. Commit `0485340`. Closes yebyen/mecris#302. **COMPLETE**.
- [x] **playwright lazy import fix (session #69)**: Moved `from playwright.sync_api import sync_playwright` inside `scrape_usage_data()`. 797 → 880 passed. Commit `c999983`. Closes yebyen/mecris#300. **COMPLETE**.
- [x] **Upstream sync + legacy-cloud ABI contract test (session #68)**: Cherry-picked AGENTS.md, created `tests/test_wasm_abi_contract_legacy.py`. Commits `a17bbc7`, `e13116e`. Closes yebyen/mecris#299. **COMPLETE**.
- [x] **Upstream sync + WASM ABI contract test (session #67)**: CI/CD evolution plan + `tests/test_wasm_abi_contract.py`. Commits `288568c`, `f66eedb`. Closes yebyen/mecris#297, #298. **COMPLETE**.
- [x] **Upstream sync (session #66)**: Merged 3 kingdonb/mecris commits. Merge commit `f967f2b`. **COMPLETE**.
- [x] **legacy-cloud branch (session #66)**: Created `legacy-cloud`, reverted WASM to Spin SDK v3. Commit `51a5fc2`. Closes yebyen/mecris#296. **COMPLETE**.
- [x] **NEON_DB_URL test failures (session #65)**: `tests/conftest.py` autouse fixture added. Closes yebyen/mecris#295. **COMPLETE**.
- [x] **narrator context presence skew (session #64)**: Fixed 3 files. Closes yebyen/mecris#294. **COMPLETE**.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [x] **URGENT: Refresh GITHUB_CLASSIC_PAT** — returns 401. Bot cannot create PRs to kingdonb/mecris. Renew in GitHub → Settings → Developer Settings → Personal access tokens (classic) with `repo` scope, update the workflow secret `GITHUB_CLASSIC_PAT`.
- [x] **Open PR yebyen:main → kingdonb:main** for session #64 commit (`10be85d`: narrator presence skew fix) and any other pending commits. Closes yebyen/mecris#294.
- [x] **Apply migrate_v8_observability.py to production Neon**: Run `python scripts/migrate_v8_observability.py` in the production environment (with NEON_DB_URL set) to add `last_status`, `last_error`, `intent` columns to `scheduler_election`.
- [x] **Apply secure_variables table to production Neon**: Run `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);` before SecretManager Neon fallback can be used in production.
- [ ] **Cloud Readiness Check**: Monitor Fermyon/Akamai for updates to their Python WASM runtimes. Test a simple SDK v4 "Hello World" to confirm when the platform has caught up.
- [ ] **Align Release Management**: Execute the plan in `docs/SPIN_V3_COMPATIBILITY_PLAN.md` to maintain a `legacy-cloud` branch providing a compatibility shim until the cloud catch-up is complete.
- [ ] **URGENT: Refresh GITHUB_CLASSIC_PAT** — returns 401. Bot cannot create PRs to kingdonb/mecris. Renew in GitHub → Settings → Developer Settings → Personal access tokens (classic) with `repo` scope, update the workflow secret `GITHUB_CLASSIC_PAT`.
- [ ] **Open PR yebyen:main → kingdonb:main** for all pending commits from sessions #64–#79 (narrator presence fix, NEON_DB_URL fix, upstream merge + legacy-cloud setup, CI/CD plan sync, ABI contract test x2, AGENTS.md sync, playwright fix, utcnow deprecation fix, async test fix, RAG test coverage, claude_monitor test coverage, billing_reconciliation test coverage, claude_monitor async path tests, get_reconciliation_summary tests, groq_odometer_tracker tests, mcp_reconcile_budget tests, claude_api_budget_scraper tests). Closes yebyen/mecris#294, #295, #296, #298, #299, #302, #303, #305, #306, #307, #308, #309, #310, #311, #312, #313.
- [ ] **Live Sunkworks session (Saturday)**: Execute dual-track tagging — tag `v0.1.0-canary.*` on main, `v0.0.1` on legacy-cloud. Run the negative E2E ABI mismatch test against Fermyon/Akamai sandbox. See `docs/CI_CD_EVOLUTION_PLAN.md` for full context.
- [ ] **CI/CD Pipeline for legacy-cloud (step 4)**: Update GitHub Actions deployment workflows to trigger Fermyon/Akamai deployments only from the `legacy-cloud` branch.
- [ ] **Cloud Readiness Check**: Monitor Fermyon/Akamai for updates to their Python WASM runtimes.
- [ ] **Apply migrate_v8_observability.py to production Neon**: Run `python scripts/migrate_v8_observability.py` in the production environment.
- [ ] **Apply secure_variables table to production Neon**: Run `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);`.
- [ ] **Verify log-message-py in Cloud**: Once platforms are ready, confirm audit logs appear in cloud KV.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Test coverage for scheduler.py** (484 lines, no scheduler-specific test file — test_scheduler_election.py only covers election logic). Key paths: timer management, task dispatch, cron parsing, presence integration.
- [ ] **AI Framework Evaluation (kingdonb/mecris#205)**: Remaining: run `scripts/evaluate_aider.py` with Aider installed and append results to `docs/AI_FRAMEWORK_EVALUATION.md`. Requires Aider + an LLM API key.
- [ ] **Budget Governor: WASM Port (kingdonb/mecris#214)**: POC complete. Remaining: Fermyon Cloud variable config — human-required for deployment.
- [ ] **Local Inference Pipeline (kingdonb/mecris#203)**: Integrate Ollama and build a cloud-fallback router.

## Infrastructure Notes (carried forward)
- **claude_api_budget_scraper.py test pattern (post-session #79)**: `ClaudeConsoleScraper()` is safe to instantiate directly (reads env vars, no DB). Use `AsyncMock` for `_load_cached_balance` / `_scaffold_scraper_implementation`. Patch `usage_tracker.UsageTracker.update_budget` for `set_manual_balance`. Use `mock_open` + `patch('os.path.exists')` for file I/O paths.
- **groq_odometer_tracker.py test pattern (post-session #77)**: `GroqOdometerTracker.__new__(GroqOdometerTracker)` + set `t.neon_url`, `t.user_id`. Patch `groq_odometer_tracker.datetime` for time-dependent tests. Patch `groq_odometer_tracker.psycopg2.connect` for DB paths. Patch `t.get_last_reading`, `t.resolve_user_id` with `patch.object`.
- **legacy-cloud playwright backport (post-session #77)**: `origin/legacy-cloud` HEAD is `2beb598` — playwright lazy import fix present. Both main and legacy-cloud tracks now have this fix.
- **get_reconciliation_summary test pattern (post-session #76)**: Use `_make_mock_cursor(provider_rows, recent_rows)` helper — sets `fetchall.side_effect = [provider_rows, recent_rows]`. Rows are plain dicts. `_make_mock_conn(mock_cursor)` wraps it. Both helpers in `tests/test_billing_reconciliation.py`.
- **claude_monitor.py test pattern (post-session #75)**: `ClaudeMonitor.__new__` + manual attrs. Twilio stub at `sys.modules` level. Async paths: `AsyncMock`. Call via `asyncio.run(m.record_usage(cost))`.
- **billing_reconciliation.py test pattern (post-session #74)**: `BillingReconciliation.__new__(BillingReconciliation)`. Set `r.budget_manager = MagicMock()`, `r.neon_url`, `r.user_id`. Patch `psycopg2.connect` for DB paths.
- **RAG test coverage (post-session #72)**: `tests/test_rag_retriever.py` (46) + `tests/test_rag_generator.py` (15). BM25 is pure-Python. RAGRetriever lazy-loads on first `retrieve()`.
- **test_narrator_context.py fixed (post-session #71)**: 6 async tests rewritten as plain pytest classes with mocked httpx. `_make_mock_context` and `_make_httpx_mock` helpers at top of file.
- **No utcnow() in Python source (post-session #70)**: All replaced with `datetime.now(timezone.utc)`.
- **Dual-track ABI contract tests (post-session #68)**: `tests/test_wasm_abi_contract.py` (main=async v4) + `tests/test_wasm_abi_contract_legacy.py` (legacy-cloud=sync v3). Legacy uses `git show origin/legacy-cloud:<path>` — skips gracefully if branch not found.
- **CI/CD evolution plan (post-session #67)**: `docs/CI_CD_EVOLUTION_PLAN.md` — dual-track: main=v4 canary, legacy-cloud=v3 stable. Negative E2E tripwire: deploy v4 component to v3 host, assert ABI crash.
- **Git history divergence note**: yebyen/mecris and kingdonb/mecris have diverged since session #66. Cherry-pick new files only.
- **conftest.py mock_usage_tracker_init (post-session #65)**: `@pytest.fixture(autouse=True)`. Patches `UsageTracker.init_database` when `NEON_DB_URL` absent.
- **narrator context presence API (post-session #64)**: `get_narrator_context` returns `presence_status` (string) and `presence` (dict). `_get_presence_summary` is the internal helper.
- **GITHUB_CLASSIC_PAT is expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately.
- **Note on Cloud Cron**: The Spin Cron trigger is currently **DISABLED** in `spin.toml`. Do not re-enable until the MCP leader can coordinate these events.
- **rag_generator model**: `claude-haiku-4-5-20251001` by default.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **Note on Cloud Cron**: The Spin Cron trigger is currently **DISABLED** in `spin.toml` to prevent it from masking local framework issues. Do not re-enable until the MCP leader can coordinate these events.
til the MCP leader can coordinate these events.
al `ANTHROPIC_API_KEY` in the MCP server env, call `ask_mecris("what is mecris?")` and confirm the `answer` field is prose (not None).
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **Note on Cloud Cron**: The Spin Cron trigger is currently **DISABLED** in `spin.toml` to prevent it from masking local framework issues. Do not re-enable until the MCP leader can coordinate these events.
- **secure_variables table**: Expected schema: `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);`. Table does NOT yet exist in production Neon.
- **SecretManager Neon fallback**: `_neon_connect` kwarg overrides `psycopg2.connect` for test injection. `HEADLESS_LOOPBACK_KEYS = ["GEMINI_API_KEY"]` is the canonical list.
- **HeadlessLoopback._SYSTEM_PASSTHROUGH**: `frozenset({"PATH", "HOME", "TERM", "USER", "SHELL", "LANG", "LC_ALL"})` — always forwarded to subprocess.
- **write_obs_status signature (Rust)**: `(connection: &Connection, user_id: &str, role: &str, last_status: &str, intent: &str, last_error: Option<&str>)`. Fail-safe on UPDATE error.
- **Observability columns are fail-safe**: `_write_obs_status()` uses a SAVEPOINT per write; rolls back if columns absent.
- **HealthChecker is backward-compatible**: Column check via `information_schema.columns`; if obs columns absent, returns `last_status/last_error/intent = None`.
- **related_bookmarks is fail-open**: If `_enrich_bookmarks_for_narrator` raises, `get_narrator_context` catches and returns `related_bookmarks: []`.
- **CopilotLoopback command**: `["gh", "copilot", "--", "-p", full_prompt]`. Default timeout: 120s.
- **budget-governor-py pure-logic API (post-session #61)**: `make_bucket_config`, `_calc_total_spent`, `_calc_window_spent`, `check_envelope`, `recommend_bucket`, `get_status`, `budget_gate` are all pure-logic, no I/O.
- **arabic-skip-counter `_count_reminders`**: Synchronous using `httpx.post` against Neon HTTP SQL API.
- **review-pump-py serialization API**: `_json_ok(data)` and `_error_json(message)`.
