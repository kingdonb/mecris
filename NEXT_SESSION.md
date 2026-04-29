# Next Session: Open PR yebyen:main → kingdonb:main (pending GITHUB_CLASSIC_PAT renewal)

## Current Status (2026-04-29, post-session #73)
- **claude_monitor.py test coverage added (session #73)**: 27 new unit tests for `_calculate_daily_burn`, `_days_until_expiry`, `CreditUsage.to_dict`, `BudgetAlert`, and `get_usage_summary` status thresholds. Suite: **968 passed, 7 skipped, 0 failed** (+27 vs 941). Commit `d4b9403`. Closes yebyen/mecris#306.
- **Test suite state**: **968 passed, 7 skipped, 0 failed** (full suite baseline in CI with complete venv).
- **GITHUB_CLASSIC_PAT still expired**: Bot cannot create PRs to kingdonb/mecris. Human must renew.
- **Upstream sync**: yebyen/mecris is ahead of kingdonb/mecris by many sessions; content was cherry-picked in sessions #67–#68. History has diverged — future syncs must cherry-pick new files only.
- **No open bot-actionable issues**: yebyen/mecris#306 is now closed. Next bot priority: billing_reconciliation.py (442 lines, 0 tests, requires Neon mock).

## Verified This Session
- [x] **claude_monitor.py test coverage (session #73)**: `tests/test_claude_monitor.py` (27 tests: 9×_calculate_daily_burn, 5×_days_until_expiry, 3×CreditUsage.to_dict, 2×BudgetAlert, 8×get_usage_summary status). Twilio stubbed via `sys.modules` at import time. `PYTHONPATH=. pytest tests/test_claude_monitor.py -v` → 27 passed. Commit `d4b9403`. Closes yebyen/mecris#306. **COMPLETE**.
- [x] **RAG test coverage (session #72)**: `tests/test_rag_retriever.py` (46 tests) + `tests/test_rag_generator.py` (15 tests). Total suite: 941 passed, 7 skipped. BM25 is pure-Python — no external deps. Commit `bc27e78`. Closes yebyen/mecris#305. **COMPLETE**.
- [x] **test_narrator_context.py async fix (session #71)**: 6 async tests inside `unittest.TestCase` rewritten as plain pytest classes with mocked httpx. Commit `b9f1bbb`. Closes yebyen/mecris#303. **COMPLETE**.
- [x] **utcnow() deprecation fix (session #70)**: `datetime.utcnow()` → `datetime.now(timezone.utc)` in 8 files (5 source + 3 test). 880 passed, 0 failed. Commit `0485340`. Closes yebyen/mecris#302. **COMPLETE**.
- [x] **playwright lazy import fix (session #69)**: Moved `from playwright.sync_api import sync_playwright` from module-level in `fetch_groq_usage.py` to inside `scrape_usage_data()`. 797 → **880 passed, 0 failed**. Commit `c999983`. Closes yebyen/mecris#300. **COMPLETE**.
- [x] **Upstream sync (session #68)**: Cherry-picked AGENTS.md from kingdonb/mecris `1caacce` + `f646174`. Commit `a17bbc7`. Closes yebyen/mecris#299 (partial).
- [x] **Legacy-cloud ABI contract test (session #68)**: `tests/test_wasm_abi_contract_legacy.py` created. 8/8 tests pass. Commit `e13116e`. Closes yebyen/mecris#299.
- [x] **Upstream sync (session #67)**: Cherry-picked `docs/CI_CD_EVOLUTION_PLAN.md` from kingdonb/mecris `d7cd7b9`. Commit `288568c`. Closes yebyen/mecris#297. **COMPLETE**.
- [x] **WASM ABI contract test (session #67)**: `tests/test_wasm_abi_contract.py` created. 8/8 tests pass. Commit `f66eedb`. Closes yebyen/mecris#298. **COMPLETE**.
- [x] **Upstream sync (session #66)**: Merged 3 kingdonb/mecris commits into yebyen/mecris main. Merge commit `f967f2b`. **COMPLETE**.
- [x] **legacy-cloud branch (session #66)**: Created `legacy-cloud` from yebyen/mecris main. Reverted all 4 WASM components to sync API. 151 passed, 0 failed. Commit `51a5fc2`. Closes yebyen/mecris#296. **COMPLETE**.
- [x] **NEON_DB_URL test failures (session #65)**: `tests/conftest.py` `mock_usage_tracker_init` autouse fixture added. Closes yebyen/mecris#295. **COMPLETE**.
- [x] **narrator context presence skew (session #64)**: Fixed 3 files. Closes yebyen/mecris#294. **COMPLETE**.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **URGENT: Refresh GITHUB_CLASSIC_PAT** — returns 401. Bot cannot create PRs to kingdonb/mecris. Renew in GitHub → Settings → Developer Settings → Personal access tokens (classic) with `repo` scope, update the workflow secret `GITHUB_CLASSIC_PAT`.
- [ ] **Open PR yebyen:main → kingdonb:main** for all pending commits from sessions #64–#73 (narrator presence fix, NEON_DB_URL fix, upstream merge + legacy-cloud setup, CI/CD plan sync, ABI contract test x2, AGENTS.md sync, playwright fix, utcnow deprecation fix, async test fix, RAG test coverage, claude_monitor test coverage). Closes yebyen/mecris#294, #295, #296, #298, #299, #302, #303, #305, #306.
- [ ] **Live Sunkworks session (Saturday)**: Execute dual-track tagging — tag `v0.1.0-canary.*` on main, `v0.0.1` on legacy-cloud. Run the negative E2E ABI mismatch test against Fermyon/Akamai sandbox. See `docs/CI_CD_EVOLUTION_PLAN.md` for full context.
- [ ] **CI/CD Pipeline for legacy-cloud (step 4)**: Update GitHub Actions deployment workflows to trigger Fermyon/Akamai deployments only from the `legacy-cloud` branch.
- [ ] **Cloud Readiness Check**: Monitor Fermyon/Akamai for updates to their Python WASM runtimes.
- [ ] **Apply migrate_v8_observability.py to production Neon**: Run `python scripts/migrate_v8_observability.py` in the production environment.
- [ ] **Apply secure_variables table to production Neon**: Run `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);`.
- [ ] **Verify log-message-py in Cloud**: Once platforms are ready, confirm audit logs appear in cloud KV.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **More test coverage gaps**: `billing_reconciliation.py` (442 lines, 0 tests — requires Neon mock). `claude_monitor.py` async paths still untested (record_usage, health_check — require file I/O mocking). Bot-actionable next session.
- [ ] **AI Framework Evaluation (kingdonb/mecris#205)**: Remaining: run `scripts/evaluate_aider.py` in an environment with Aider installed and append results to `docs/AI_FRAMEWORK_EVALUATION.md` evidence log. Requires Aider + an LLM API key.
- [ ] **Budget Governor: WASM Port (kingdonb/mecris#214)**: POC complete and wired into spin.toml. Remaining: Fermyon Cloud variable config — human-required for deployment.
- [ ] **Local Inference Pipeline (kingdonb/mecris#203)**: Integrate Ollama and build a cloud-fallback router.
- [ ] **Backporting workflow (legacy-cloud step 5)**: Backport `fetch_groq_usage.py` playwright lazy import fix (`c999983`) to `legacy-cloud` branch.

## Infrastructure Notes (carried forward)
- **claude_monitor.py test pattern (post-session #73)**: Twilio has no package in stripped CI env. Stub at `sys.modules` level in test file: `sys.modules.setdefault("twilio", types.ModuleType("twilio"))` + `sys.modules.setdefault("twilio.rest", _twilio_rest_stub)`. Use `ClaudeMonitor.__new__(ClaudeMonitor)` to bypass `__init__` (avoids env var reads and httpx client creation). Set `m.budget_limit`, `m.expiry_date`, `m.alerts = []`, `m.client = MagicMock()` manually.
- **RAG test coverage (post-session #72)**: `tests/test_rag_retriever.py` (46 tests) + `tests/test_rag_generator.py` (15 tests). Total suite: 941 passed, 7 skipped. BM25 is pure-Python — no external deps. RAGRetriever lazy-loads on first `retrieve()`; `reset()` forces re-index. `generate_answer` is fail-open (returns None if ANTHROPIC_API_KEY absent or API raises).
- **test_narrator_context.py fixed (post-session #71)**: 6 async tests inside `unittest.TestCase` rewritten as plain pytest classes with mocked httpx. `_make_mock_context` and `_make_httpx_mock` helpers added at top of file.
- **No utcnow() in Python source (post-session #70)**: All `datetime.utcnow()` calls replaced with `datetime.now(timezone.utc)`. If new code is written, use `timezone.utc` pattern.
- **Dual-track ABI contract tests (post-session #68)**: `tests/test_wasm_abi_contract.py` (main=async v4, 8 tests) + `tests/test_wasm_abi_contract_legacy.py` (legacy-cloud=sync v3, 8 tests). Legacy test uses `git show origin/legacy-cloud:<path>` — skips gracefully if branch not found.
- **CI/CD evolution plan (post-session #67)**: `docs/CI_CD_EVOLUTION_PLAN.md` — dual-track: main=v4 canary, legacy-cloud=v3 stable. Negative E2E tripwire: deploy v4 component to v3 host, assert ABI crash. When tripwire suddenly passes, cloud has upgraded to v4 → sunset legacy-cloud.
- **Git history divergence note**: yebyen/mecris and kingdonb/mecris have diverged histories since session #66. Future upstream syncs should cherry-pick new files only.
- **conftest.py mock_usage_tracker_init (post-session #65)**: `@pytest.fixture(autouse=True)`. When `NEON_DB_URL` absent: resets `usage_tracker._tracker_instance = None` and patches `UsageTracker.init_database = lambda self: None`. Conditional on `NEON_DB_URL` absence.
- **narrator context presence API (post-session #64)**: `get_narrator_context` returns `presence_status` (string) and `presence` (dict). `_get_presence_summary` (not `_get_presence_status`) is the internal helper.
- **GITHUB_CLASSIC_PAT is expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately.
- **Note on Cloud Cron**: The Spin Cron trigger is currently **DISABLED** in `spin.toml`. Do not re-enable until the MCP leader can coordinate these events.
- **rag_generator model**: `claude-haiku-4-5-20251001` by default.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **secure_variables table**: Expected schema: `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);`. Table does NOT yet exist in production Neon.
- **SecretManager Neon fallback**: `_neon_connect` kwarg overrides `psycopg2.connect` for test injection. `HEADLESS_LOOPBACK_KEYS = ["GEMINI_API_KEY"]` is the canonical list.
- **HeadlessLoopback._SYSTEM_PASSTHROUGH**: `frozenset({"PATH", "HOME", "TERM", "USER", "SHELL", "LANG", "LC_ALL"})` — always forwarded to subprocess.
- **write_obs_status signature (Rust)**: `(connection: &Connection, user_id: &str, role: &str, last_status: &str, intent: &str, last_error: Option<&str>)`. Fail-safe on UPDATE error.
- **Observability columns are fail-safe**: `_write_obs_status()` uses a SAVEPOINT per write; if columns absent, rolls back, sets `_has_obs_columns = False`, logs at DEBUG.
- **HealthChecker is backward-compatible**: Column check via `information_schema.columns`; if obs columns absent, returns `last_status/last_error/intent = None`.
- **related_bookmarks is fail-open**: If `_enrich_bookmarks_for_narrator` raises, `get_narrator_context` catches, logs a warning, and returns `related_bookmarks: []`.
- **CopilotLoopback command**: `["gh", "copilot", "--", "-p", full_prompt]`. Default timeout: 120s.
- **budget-governor-py pure-logic API (post-session #61)**: `make_bucket_config`, `_calc_total_spent`, `_calc_window_spent`, `check_envelope`, `recommend_bucket`, `get_status`, `budget_gate` are all pure-logic, no I/O.
- **arabic-skip-counter `_count_reminders`**: Synchronous using `httpx.post` against Neon HTTP SQL API.
- **review-pump-py serialization API**: `_json_ok(data)` and `_error_json(message)`.
