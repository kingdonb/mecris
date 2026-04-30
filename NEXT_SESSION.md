# Next Session: Remaining scheduler.py paths + AI Framework Evaluation

## Current Status (2026-04-30, post-session #80)
- **scheduler.py test coverage (session #80)**: 24 new tests in `tests/test_scheduler_jobs.py` — global background jobs (11: reminder×3, language_sync×2, walk_sync×3, archivist×2, cooperative_monitor×1) + MecrisScheduler methods (13: __init__×1, start×2, _init_db×1, _attempt_leadership×1, _stop_leader_jobs×2, enqueue_delayed_message×2, get_queue×2, shutdown×2). All 24 passed in 0.29s. Full scheduler suite: 32 passed. Commit `a363bc0`. Closes yebyen/mecris#314.
- **Full scheduler suite**: 32 tests across 3 files (test_scheduler_election×6, test_scheduler_timer_reset×2, test_scheduler_jobs×24) — all passing.
- **GITHUB_CLASSIC_PAT still expired**: Bot cannot create PRs to kingdonb/mecris. Human must renew.
- **Upstream sync**: yebyen/mecris is ahead of kingdonb/mecris by many sessions; history has diverged since session #66. Future syncs must cherry-pick new files only.
- **Known bug in scheduler.py**: `attempt` variable referenced at line 334 in `_attempt_leadership` (heartbeat-maintenance branch) is not defined in that scope — would raise `NameError` if hit. Noted but not fixed (out of scope).

## Verified This Session
- [x] **scheduler.py test coverage (session #80)**: `tests/test_scheduler_jobs.py` — 24 tests (global_reminder_job×3, global_language_sync_job×2, global_walk_sync_job×3, global_archivist_job×2, global_cooperative_monitor_job×1, MecrisScheduler.__init__×1, start×2, _init_db×1, _attempt_leadership×1, _stop_leader_jobs×2, enqueue_delayed_message×2, get_queue×2, shutdown×2). `PYTHONPATH=. python3 -m pytest tests/test_scheduler_jobs.py -v` → 24 passed in 0.29s. Full suite (32 tests) also green. Commit `a363bc0`. Closes yebyen/mecris#314. **COMPLETE**.
- [x] **claude_api_budget_scraper.py test coverage (session #79)**: `tests/test_claude_api_budget_scraper.py` — 24 tests. All 24 passed in 0.32s. Commit `594b309`. Closes yebyen/mecris#313. **COMPLETE**.
- [x] **mcp_reconcile_budget.py test coverage (session #78)**: `tests/test_mcp_reconcile_budget.py` — 18 tests. All 18 passed. Commit `2c19849`. Closes yebyen/mecris#312. **COMPLETE**.
- [x] **legacy-cloud playwright backport (session #77)**: `git log origin/legacy-cloud | head -1` → `2beb598 fix(imports): make playwright import lazy in fetch_groq_usage.py`. Closes yebyen/mecris#310. **COMPLETE**.
- [x] **groq_odometer_tracker.py test coverage (session #77)**: `tests/test_groq_odometer_tracker.py` — 24 tests. Commit `c60c78a`. Closes yebyen/mecris#311. **COMPLETE**.
- [x] **billing_reconciliation.get_reconciliation_summary tests (session #76)**: 6 new tests — 41 total. Commit `7a69b2d`. Closes yebyen/mecris#309.
- [x] **claude_monitor.py async path tests (session #75)**: 41 tests total. Commit `721bfd1`. Closes yebyen/mecris#308. **COMPLETE**.
- [x] **billing_reconciliation.py test coverage (session #74)**: 35 tests. Commit `d41a848`. Closes yebyen/mecris#307. **COMPLETE**.
- [x] **claude_monitor.py test coverage (session #73)**: 27 tests. Commit `d4b9403`. Closes yebyen/mecris#306. **COMPLETE**.
- [x] **RAG test coverage (session #72)**: `tests/test_rag_retriever.py` (46) + `tests/test_rag_generator.py` (15). Commit `bc27e78`. Closes yebyen/mecris#305. **COMPLETE**.
- [x] **test_narrator_context.py async fix (session #71)**: Commit `b9f1bbb`. Closes yebyen/mecris#303. **COMPLETE**.
- [x] **utcnow() deprecation fix (session #70)**: Commit `0485340`. Closes yebyen/mecris#302. **COMPLETE**.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **URGENT: Refresh GITHUB_CLASSIC_PAT** — returns 401. Bot cannot create PRs to kingdonb/mecris. Renew in GitHub → Settings → Developer Settings → Personal access tokens (classic) with `repo` scope, update the workflow secret `GITHUB_CLASSIC_PAT`.
- [ ] **Open PR yebyen:main → kingdonb:main** for all pending commits from sessions #64–#80 (narrator presence fix, NEON_DB_URL fix, upstream merge + legacy-cloud setup, CI/CD plan sync, ABI contract test x2, AGENTS.md sync, playwright fix, utcnow deprecation fix, async test fix, RAG test coverage, claude_monitor test coverage, billing_reconciliation test coverage, claude_monitor async path tests, get_reconciliation_summary tests, groq_odometer_tracker tests, mcp_reconcile_budget tests, claude_api_budget_scraper tests, scheduler background job tests). Closes yebyen/mecris#294, #295, #296, #298, #299, #302, #303, #305, #306, #307, #308, #309, #310, #311, #312, #313, #314.
- [ ] **Cloud Readiness Check**: Monitor Fermyon/Akamai for updates to their Python WASM runtimes. Test a simple SDK v4 "Hello World" to confirm when the platform has caught up.
- [ ] **Align Release Management**: Execute the plan in `docs/SPIN_V3_COMPATIBILITY_PLAN.md` to maintain a `legacy-cloud` branch providing a compatibility shim until the cloud catch-up is complete.
- [ ] **Live Sunkworks session (Saturday)**: Execute dual-track tagging — tag `v0.1.0-canary.*` on main, `v0.0.1` on legacy-cloud. Run the negative E2E ABI mismatch test against Fermyon/Akamai sandbox. See `docs/CI_CD_EVOLUTION_PLAN.md` for full context.
- [ ] **CI/CD Pipeline for legacy-cloud (step 4)**: Update GitHub Actions deployment workflows to trigger Fermyon/Akamai deployments only from the `legacy-cloud` branch.
- [ ] **Apply migrate_v8_observability.py to production Neon**: Run `python scripts/migrate_v8_observability.py` in the production environment.
- [ ] **Apply secure_variables table to production Neon**: Run `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);`.
- [ ] **Verify log-message-py in Cloud**: Once platforms are ready, confirm audit logs appear in cloud KV.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Fix NameError bug in scheduler.py:334** — `attempt` variable used in heartbeat-maintenance branch of `_attempt_leadership` is not defined in scope. Should be a counter tracked outside the while loop or removed. Add a regression test once fixed.
- [ ] **Test coverage for _start_leader_jobs** — not yet tested (requires async APScheduler integration; skipped this session as it needs real or deeply-mocked scheduler). Key paths: jobs already registered (idempotent), locked DB retry loop.
- [ ] **AI Framework Evaluation (kingdonb/mecris#205)**: Remaining: run `scripts/evaluate_aider.py` with Aider installed and append results to `docs/AI_FRAMEWORK_EVALUATION.md`. Requires Aider + an LLM API key.
- [ ] **Budget Governor: WASM Port (kingdonb/mecris#214)**: POC complete. Remaining: Fermyon Cloud variable config — human-required for deployment.
- [ ] **Local Inference Pipeline (kingdonb/mecris#203)**: Integrate Ollama and build a cloud-fallback router.

## Infrastructure Notes (carried forward)
- **scheduler.py NameError bug (post-session #80)**: Line 334 references `attempt` variable inside the heartbeat-maintenance else-branch of `_attempt_leadership`, but `attempt` is not defined in that scope. This branch is reached when `is_leader=True` and `row[0]==process_id`. Would raise `NameError` in production but is not hit in current tests.
- **scheduler test pattern (post-session #80)**: `_fresh_scheduler()` helper via `MecrisScheduler.__new__` sets neon_url, user_id, process_id, is_leader, running, _election_task, _has_obs_columns, scheduler (MagicMock). Global background job tests use `patch.dict(sys.modules, {'mcp_server': mock_mcp})` — imports inside function body pick up from sys.modules.
- **claude_api_budget_scraper.py test pattern (post-session #79)**: `ClaudeConsoleScraper()` is safe to instantiate directly (reads env vars, no DB). Use `AsyncMock` for `_load_cached_balance` / `_scaffold_scraper_implementation`. Patch `usage_tracker.UsageTracker.update_budget` for `set_manual_balance`. Use `mock_open` + `patch('os.path.exists')` for file I/O paths.
- **groq_odometer_tracker.py test pattern (post-session #77)**: `GroqOdometerTracker.__new__(GroqOdometerTracker)` + set `t.neon_url`, `t.user_id`. Patch `groq_odometer_tracker.datetime` for time-dependent tests. Patch `groq_odometer_tracker.psycopg2.connect` for DB paths. Patch `t.get_last_reading`, `t.resolve_user_id` with `patch.object`.
- **legacy-cloud playwright backport (post-session #77)**: `origin/legacy-cloud` HEAD is `2beb598` — playwright lazy import fix present. Both main and legacy-cloud tracks now have this fix.
- **get_reconciliation_summary test pattern (post-session #76)**: Use `_make_mock_cursor(provider_rows, recent_rows)` helper — sets `fetchall.side_effect = [provider_rows, recent_rows]`. Rows are plain dicts. `_make_mock_conn(mock_cursor)` wraps it. Both helpers in `tests/test_billing_reconciliation.py`.
- **claude_monitor.py test pattern (post-session #75)**: `ClaudeMonitor.__new__` + manual attrs. Twilio stub at `sys.modules` level. Async paths: `AsyncMock`. Call via `asyncio.run(m.record_usage(cost))`.
- **billing_reconciliation.py test pattern (post-session #74)**: `BillingReconciliation.__new__(BillingReconciliation)`. Set `r.budget_manager = MagicMock()`, `r.neon_url`, `r.user_id`. Patch `psycopg2.connect` for DB paths.
- **RAG test coverage (post-session #72)**: `tests/test_rag_retriever.py` (46) + `tests/test_rag_generator.py` (15). BM25 is pure-Python. RAGRetriever lazy-loads on first `retrieve()`.
- **test_narrator_context.py fixed (post-session #71)**: 6 async tests rewritten as plain pytest classes with mocked httpx. `_make_mock_context` and `_make_httpx_mock` helpers at top of file.
- **No utcnow() in Python source (post-session #70)**: All replaced with `datetime.now(timezone.utc)`.
- **Dual-track ABI contract tests (post-session #68)**: `tests/test_wasm_abi_contract.py` (main=async v4) + `tests/test_wasm_abi_contract_legacy.py` (legacy-cloud=sync v3).
- **CI/CD evolution plan (post-session #67)**: `docs/CI_CD_EVOLUTION_PLAN.md` — dual-track: main=v4 canary, legacy-cloud=v3 stable.
- **Git history divergence note**: yebyen/mecris and kingdonb/mecris have diverged since session #66. Cherry-pick new files only.
- **conftest.py mock_usage_tracker_init (post-session #65)**: `@pytest.fixture(autouse=True)`. Patches `UsageTracker.init_database` when `NEON_DB_URL` absent.
- **GITHUB_CLASSIC_PAT is expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately.
- **Note on Cloud Cron**: The Spin Cron trigger is currently **DISABLED** in `spin.toml`. Do not re-enable until the MCP leader can coordinate these events.
- **rag_generator model**: `claude-haiku-4-5-20251001` by default.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **secure_variables table**: Expected schema: `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);`. Table does NOT yet exist in production Neon.
- **SecretManager Neon fallback**: `_neon_connect` kwarg overrides `psycopg2.connect` for test injection. `HEADLESS_LOOPBACK_KEYS = ["GEMINI_API_KEY"]` is the canonical list.
- **HeadlessLoopback._SYSTEM_PASSTHROUGH**: `frozenset({"PATH", "HOME", "TERM", "USER", "SHELL", "LANG", "LC_ALL"})` — always forwarded to subprocess.
- **write_obs_status signature (Rust)**: `(connection: &Connection, user_id: &str, role: &str, last_status: &str, intent: &str, last_error: Option<&str>)`. Fail-safe on UPDATE error.
- **Observability columns are fail-safe**: `_write_obs_status()` uses a SAVEPOINT per write; rolls back if columns absent.
- **HealthChecker is backward-compatible**: Column check via `information_schema.columns`; if obs columns absent, returns `last_status/last_error/intent = None`.
- **related_bookmarks is fail-open**: If `_enrich_bookmarks_for_narrator` raises, `get_narrator_context` catches and returns `related_bookmarks: []`.
- **budget-governor-py pure-logic API (post-session #61)**: `make_bucket_config`, `_calc_total_spent`, `_calc_window_spent`, `check_envelope`, `recommend_bucket`, `get_status`, `budget_gate` are all pure-logic, no I/O.
