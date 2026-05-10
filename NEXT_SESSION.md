# Next Session: Human Yield bin/mecris presence CLI (kingdonb/mecris#211) or next bug hunt

## Current Status (2026-05-10, post-session #101)
- **Bus Standardization (session #101)**: COMPLETE. `fetch_system_pulse()` now SELECTs `last_status`, `intent`, `last_error` from `scheduler_election`. Graceful fallback SQL (NULL values) when migration v8 columns absent. 6 tests in `tests/test_system_pulse.py` pass. Commit `a410df8`. Closes yebyen/mecris#337.
- **Observability Mandate Python layer (kingdonb/mecris#245)**: COMPLETE end-to-end. `_write_obs_status()` writes obs fields to DB → `fetch_system_pulse()` reads them back → modalities include `last_status`/`intent`/`last_error`. In-memory mirror also populated via `get_narrator_context` `system_pulse`.
- **GITHUB_CLASSIC_PAT still expired**: Bot cannot create PRs to kingdonb/mecris. Human must renew.
- **Upstream sync**: yebyen/mecris is ahead of kingdonb/mecris by many sessions (#80–#101); history has diverged since session #66. Future syncs must cherry-pick new files only.

## Verified This Session
- [x] **Bus Standardization (session #101)**: `PYTHONPATH=. pytest tests/test_system_pulse.py -v` → 6 passed in 1.64s. `fetch_system_pulse()` in `mcp_server.py` now SELECTs 6 columns (role, heartbeat, minutes_since, last_status, intent, last_error) with SAVEPOINT-style fallback to NULL when migration v8 columns absent. Each modality dict includes the three obs fields. Regression: `test_mcp_server.py` + `test_daily_aggregate_status.py` → 19 passed. Commit `a410df8`. Closes yebyen/mecris#337.
- [x] **test_presence_neon.py psycopg2 bootstrap (session #100)**: `PYTHONPATH=. pytest tests/test_ghost_presence.py tests/test_presence_scheduler.py tests/test_presence_neon.py -v` → 54 passed in 0.22s. Commit `83f6b0a`. Closes yebyen/mecris#336.
- [x] **obs in-memory mirror (session #99)**: 13 tests passed. `MecrisScheduler` now has `last_status`, `intent`, `last_error` attrs mirrored by `_write_obs_status()`. Commit `1c78824`. Closes yebyen/mecris#335.
- [x] **psycopg2 bootstrap fix (session #98)**: 19 passed. Commit `5e9df24`.
- [x] **whatsapp_template_manager.py test coverage (session #97)**: 11 tests. Commit `9126bbf`. Closes yebyen/mecris#333.
- [x] **initialize_neon.py test coverage (session #96)**: 3 tests. Commit `4f765ab`. Closes yebyen/mecris#332.
- [x] **Full scripts coverage**: ALL scripts now covered. Only intentional skips remain.
- [x] **migrate_pii_encryption.py + migrate_review_pump.py (session #95)**: 12 tests. Commit `e9c1688`. Closes yebyen/mecris#331.
- [x] **base_walk_reminder.py test coverage (session #94)**: 16 tests. Commit `4107364`. Closes yebyen/mecris#329.
- [x] **ClozemasterScraper test coverage (session #93)**: 28 tests. Commit `f66bf15`.
- [x] **bump_version/check_neon_budget/cloud_enable_beeminder (session #92)**: 35 tests. Commit `1a1732b`. Closes yebyen/mecris#327.
- [x] **verify_docs_graph.py (session #91)**: 35 tests. Commit `e98b69a`. Closes yebyen/mecris#326.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **URGENT: Refresh GITHUB_CLASSIC_PAT** — returns 401. Bot cannot create PRs to kingdonb/mecris. Renew in GitHub → Settings → Developer Settings → Personal access tokens (classic) with `repo` scope, update the workflow secret `GITHUB_CLASSIC_PAT`.
- [ ] **Open PR yebyen:main → kingdonb:main** for all pending commits from sessions #64–#101 (now includes Bus Standardization `a410df8`). Closes yebyen/mecris#294, #295, #296, #298, #299, #302, #303, #305, #306, #307, #308, #309, #310, #311, #312, #313, #314, #315, #316, #317, #318, #319, #320, #322, #323, #324, #325, #326, #327, #328, #329, #331, #332, #333, #334, #335, #337.
- [ ] **Apply migrate_v8_observability.py to production Neon**: Run `python scripts/migrate_v8_observability.py` in the production environment. Required before `fetch_system_pulse` returns non-NULL obs fields from DB.
- [ ] **Apply secure_variables table to production Neon**: Run `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);`.
- [ ] **Cloud Readiness Check**: Monitor Fermyon/Akamai for updates to their Python WASM runtimes.
- [ ] **Align Release Management**: Execute the plan in `docs/SPIN_V3_COMPATIBILITY_PLAN.md`.
- [ ] **Live Sunkworks session (Saturday)**: Dual-track tagging — `v0.1.0-canary.*` on main, `v0.0.1` on legacy-cloud. See `docs/CI_CD_EVOLUTION_PLAN.md`.
- [ ] **CI/CD Pipeline for legacy-cloud (step 4)**: Update GitHub Actions deployment workflows.
- [ ] **Verify log-message-py in Cloud**: Once platforms are ready, confirm audit logs appear in cloud KV.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Human Yield / Presence Detection (kingdonb/mecris#211)**: Implement `bin/mecris presence` command or background thread with lock file mechanism (`/tmp/mecris_presence.lock`). Detect active terminal session, respect lock in `MecrisScheduler`. Write unit tests for presence detection logic (pure Python, no I/O deps). Note: `ghost/presence.py` + `cli/main.py presence` subcommand + scheduler integration already complete; this item is the `bin/mecris presence` CLI wrapper.
- [ ] **Observability Mandate non-Python (kingdonb/mecris#245)**: Rust WASM `sync-service/src/lib.rs` Silent Decision logging (non-bot-actionable) and Android `HeartbeatWorker` obs fields (non-bot-actionable). Python layer is fully COMPLETE.
- [ ] **AI Framework Evaluation (kingdonb/mecris#205)**: Run `scripts/evaluate_aider.py` with Aider installed. Requires Aider + LLM API key.
- [ ] **Budget Governor: WASM Port (kingdonb/mecris#214)**: POC complete. Remaining: Fermyon Cloud variable config — human-required for deployment.
- [ ] **Local Inference Pipeline (kingdonb/mecris#203)**: Integrate Ollama and build a cloud-fallback router.

## Infrastructure Notes (carried forward)
- **fetch_system_pulse() obs fields (post-session #101)**: SQL now SELECTs `last_status`, `intent`, `last_error` from `scheduler_election`. On column-missing exception, falls back to a NULL-only SELECT. Each modality dict includes `last_status`, `intent`, `last_error` keys (may be None if migration v8 not applied or fields not yet written). Test pattern: `patch("psycopg2.connect", return_value=conn)` with 6-tuple rows; `sys.modules.pop("mcp_server", None)` + re-import per test. Commit `a410df8`.
- **obs in-memory mirror (post-session #99)**: `MecrisScheduler` now has `last_status: Optional[str] = None`, `intent: Optional[str] = None`, `last_error: Optional[str] = None`. `_write_obs_status()` updates them immediately after `RELEASE SAVEPOINT obs_write`. `get_narrator_context` `system_pulse` key includes all three. Commit `1c78824`.
- **test_system_pulse.py pattern (post-session #101)**: No sys.modules bootstrap needed (real psycopg2-binary installed). Use `patch("psycopg2.connect", return_value=conn)` directly. `_make_conn_mock(rows)` helper: cur+conn with `__enter__`/`__exit__` + `fetchall.return_value = rows`. Import with NEON_DB_URL set for module-level init, then call without NEON_DB_URL for early-return test. `sys.modules.pop("mcp_server", None)` required per test to reset import state.
- **test_system_health.py + test_health_checker.py bootstrap pattern (post-session #98)**: Both files now have `_mock_psycopg2 = MagicMock(); sys.modules.setdefault("psycopg2", _mock_psycopg2)` at module level. Commit `5e9df24`.
- **scheduler.py NameError fixed (post-session #81)**: Line 334 `if attempt % 20 == 0:` removed. Heartbeat logs unconditionally every cycle. Commit `8f0026a`.
- **rag_generator model**: `claude-haiku-4-5-20251001` by default.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning.
- **secure_variables table**: Expected schema: `CREATE TABLE IF NOT EXISTS secure_variables (key TEXT PRIMARY KEY, value TEXT NOT NULL);`. Table does NOT yet exist in production Neon.
- **SecretManager Neon fallback**: `_neon_connect` kwarg overrides `psycopg2.connect` for test injection. `HEADLESS_LOOPBACK_KEYS = ["GEMINI_API_KEY"]` is the canonical list.
- **write_obs_status signature (Rust)**: `(connection: &Connection, user_id: &str, role: &str, last_status: &str, intent: &str, last_error: Option<&str>)`. Fail-safe on UPDATE error.
- **budget-governor-py pure-logic API (post-session #61)**: `make_bucket_config`, `_calc_total_spent`, `_calc_window_spent`, `check_envelope`, `recommend_bucket`, `get_status`, `budget_gate` are all pure-logic, no I/O.
- **Git history divergence note**: yebyen/mecris and kingdonb/mecris have diverged since session #66. Cherry-pick new files only.
- **Note on Cloud Cron**: The Spin Cron trigger is currently **DISABLED** in `spin.toml`. Do not re-enable until the MCP leader can coordinate these events.
- **GITHUB_CLASSIC_PAT is expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately.
