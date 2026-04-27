# Next Session: Open PRs to kingdonb/mecris (human-required) or bot-actionable: notification_prefs write path or AI Framework Evaluation

## Current Status (2026-04-27, post-session #57)
- **JIT Secret Manager COMPLETE**: `services/secret_manager.py` created with `SecretManager.get_secrets(keys)`. `HeadlessLoopback` now builds a minimal subprocess env (system passthrough vars + only requested API keys) and passes `env=` explicitly to `subprocess.Popen`. 16 new tests; 40 headless-related tests total pass. Committed `4846e5e`. Closes yebyen/mecris#286. Toward kingdonb/mecris#204.
- **kingdonb/mecris#204 (JIT Secret Manager) is COMPLETE** in yebyen/mecris: `SecretManager` abstraction + `HeadlessLoopback` env isolation implemented and tested.
- **GITHUB_CLASSIC_PAT still expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately (human-required). Blocks all PRs.
- **yebyen/mecris ahead of kingdonb/mecris by ~8 commits**: TF-IDF Search, Narrator enrichment, Observability Phase 1 (Python), Observability Phase 2 Python + Rust, notification_prefs, JIT Secret Manager. None yet PRed due to expired PAT.

## Verified This Session
- [x] **JIT Secret Manager (session #57)**: `SecretManager.get_secrets` returns only requested keys; `HeadlessLoopback._build_subprocess_env()` assembles minimal env with `_SYSTEM_PASSTHROUGH` + secrets from `SecretManager`; parent `os.environ` not modified. 16 tests pass (8 SecretManager, 5 env-isolation, 3 parent-env). All 24 prior headless_loopback tests still pass. **COMPLETE** — closes yebyen/mecris#286, toward kingdonb/mecris#204.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **URGENT: Refresh GITHUB_CLASSIC_PAT** — returns 401. Bot cannot create PRs to kingdonb/mecris. Renew in GitHub → Settings → Developer Settings → Personal access tokens (classic) with `repo` scope, update the workflow secret `GITHUB_CLASSIC_PAT`.
- [ ] **Open PR yebyen:main → kingdonb:main** for all pending commits (TF-IDF Search, Narrator enrichment, Observability Phase 1+2 Python, Observability Phase 2 Rust, notification_prefs, JIT Secret Manager) — blocked by expired PAT. Closes kingdonb/mecris#167, kingdonb/mecris#169, kingdonb/mecris#204, kingdonb/mecris#208 (complete), kingdonb/mecris#245 (Phase 1 + Phase 2 Python + Phase 2 Rust req 3).
- [ ] **Apply migrate_v8_observability.py to production Neon**: Run `python scripts/migrate_v8_observability.py` in the production environment (with NEON_DB_URL set) to add `last_status`, `last_error`, `intent` columns to `scheduler_election`.
- [ ] **Cloud Readiness Check**: Monitor Fermyon/Akamai for updates to their Python WASM runtimes. Test a simple SDK v4 "Hello World" to confirm when the platform has caught up.
- [ ] **Align Release Management**: Determine if we should maintain a "Legacy Cloud" branch or implement a compatibility shim until the cloud catch-up is complete.
- [ ] **Verify log-message-py in Cloud**: Once platforms are ready, confirm audit logs appear in cloud KV.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **notification_prefs write path**: The `notification_prefs` JSONB column is read by the Rust reminder engine but there is no endpoint to write/update it. Add a `PATCH /profile` field or MCP tool to set per-user notification prefs. Good bounded Rust task (~30 min).
- [ ] **AI Framework Evaluation (kingdonb/mecris#205)**: Matrix doc and POC script committed (`1a459aa`). Remaining: run `scripts/evaluate_aider.py` in an environment with Aider installed and append results to `docs/AI_FRAMEWORK_EVALUATION.md` evidence log. Requires Aider + an LLM API key.
- [ ] **Budget Governor: WASM Port (kingdonb/mecris#214)**: POC complete and wired into spin.toml. Remaining: Fermyon Cloud variable config — human-required for deployment.
- [ ] **Local Inference Pipeline (kingdonb/mecris#203)**: Integrate Ollama and build a cloud-fallback router.
- [ ] **SecretManager Neon fallback**: `services/secret_manager.py` currently reads only from `os.environ`. Future extension: if a key is absent and `NEON_DB_URL` is set, look it up from a Neon-backed secure-variable store. No code change needed now; extension point is in `get_secrets()`.

## Infrastructure Notes (carried forward)
- **`SecretManager` extension point**: Add Neon-backed fallback in `get_secrets()` without breaking any call sites. `HEADLESS_LOOPBACK_KEYS = ["GEMINI_API_KEY"]` is the canonical list; extend it if more keys are needed by the subprocess.
- **`HeadlessLoopback._SYSTEM_PASSTHROUGH`**: `frozenset({"PATH", "HOME", "TERM", "USER", "SHELL", "LANG", "LC_ALL"})` — always forwarded to subprocess. No credentials in this set.
- **`notification_prefs` JSONB keys**: `step_threshold` (u32), `window_start_hour` (u32), `window_end_hour` (u32), `rate_limit_minutes` (u64). All optional; any absent key falls back to default (2000 / 8 / 20 / 240). Empty `{}` or NULL → all defaults.
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
