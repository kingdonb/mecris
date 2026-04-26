# Next Session: Open PRs to kingdonb/mecris (human-required) or bot-actionable: Observability Phase 2 (Rust/scheduler reporting) or Twilio WASM

## Current Status (2026-04-26, post-session #53)
- **Observability Mandate Phase 1 COMPLETE**: `scripts/migrate_v8_observability.py` (idempotent ALTER TABLE for `last_status`, `last_error`, `intent`), `services/health_checker.py` updated to detect and return obs fields (backward-compatible with pre-migration), `scheduler.py` writes `last_status`/`intent` on election claim and heartbeat via SAVEPOINT helper. 13 unit tests in `tests/test_health_checker.py`, all passing. Committed `9020007`. Closes yebyen/mecris#282. Toward kingdonb/mecris#245 (phase 1 complete).
- **GITHUB_CLASSIC_PAT still expired**: Bot cannot create PRs to kingdonb/mecris. Renew immediately (human-required). Blocks all PRs.
- **yebyen/mecris ahead of kingdonb/mecris by 4 commits**: `5be5a79` (TF-IDF Search), `18b0aa6` (archive #51), `f91710b` (Narrator enrichment), `9020007` (Observability Phase 1). None yet PRed due to expired PAT.

## Verified This Session
- [x] **Observability Mandate Phase 1 (session #53)**: `scripts/migrate_v8_observability.py` + `HealthChecker` obs fields + `scheduler.py` `_write_obs_status()` helper. `PYTHONPATH=. python3 -m pytest tests/test_health_checker.py -v` → 13 passed, 0 failures. **COMPLETE** — closes yebyen/mecris#282, toward kingdonb/mecris#245.
- [x] **No regression**: `tests/test_narrator_bookmark_enrichment.py` (8 tests) + `tests/test_ask_mecris.py` (39 tests) + `tests/test_health_checker.py` (13 tests) — 60 total, all pass.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **URGENT: Refresh GITHUB_CLASSIC_PAT** — returns 401. Bot cannot create PRs to kingdonb/mecris. Renew in GitHub → Settings → Developer Settings → Personal access tokens (classic) with `repo` scope, update the workflow secret `GITHUB_CLASSIC_PAT`.
- [ ] **Open PR yebyen:main → kingdonb:main** for `5be5a79` (Semantic Search), `f91710b` (Narrator enrichment), `9020007` (Observability Phase 1), `0a29cc7` (Chrome Bookmarks), `139d67f` (CopilotLoopback), and `e6a0bb4` (Spin SDK v4) — all blocked by expired PAT. Closes kingdonb/mecris#208 (complete), #201 (Chrome), #206 (CopilotLoopback), #213 (Spin SDK v4), and partially #245 (Observability Phase 1 only).
- [ ] **Apply migrate_v8_observability.py to production Neon**: Run `python scripts/migrate_v8_observability.py` in the production environment (with NEON_DB_URL set) to add `last_status`, `last_error`, `intent` columns to `scheduler_election`.
- [ ] **Cloud Readiness Check**: Monitor Fermyon/Akamai for updates to their Python WASM runtimes. Test a simple SDK v4 "Hello World" to confirm when the platform has caught up.
- [ ] **Align Release Management**: Determine if we should maintain a "Legacy Cloud" branch or implement a compatibility shim until the cloud catch-up is complete.
- [ ] **Verify log-message-py in Cloud**: Once platforms are ready, confirm audit logs appear in cloud KV.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Observability Phase 2 — Rust WASM Backend (kingdonb/mecris#245 req 3)**: Update `sync-service/src/lib.rs` to record every "Silent Decision" (stand-downs) into `scheduler_election.last_status`. Requires Rust/WASM changes.
- [ ] **Observability Phase 2 — scheduler.py `last_error` writes (kingdonb/mecris#245 req 4)**: Extend `_write_obs_status()` to also write `last_error` when exceptions occur in leader jobs; expand tests.
- [ ] **Port Twilio to WASM Brain (Issue #167)**: Move SMS/WhatsApp dispatch logic from Python/boris-fiona-walker into the `sync-service` Rust module.
- [ ] **Rust Reminder Engine (Issue #169)**: Implement the 2000-step threshold, sleep window heuristics, and weather checks natively in Rust.
- [ ] **AI Framework Evaluation (Issue #205)**: Matrix doc and POC script committed (`1a459aa`). Remaining: run `scripts/evaluate_aider.py` in an environment with Aider installed and append results to `docs/AI_FRAMEWORK_EVALUATION.md` evidence log. Requires Aider + an LLM API key.
- [ ] **Budget Governor: WASM Port (Issue #214)**: POC complete and wired into spin.toml. Remaining: Fermyon Cloud variable config — human-required for deployment.
- [ ] **Autonomous Security: JIT Secret Manager (Issue #204)**: Implement secure credential retrieval for headless `gemini --yolo` turns.
- [ ] **Local Inference Pipeline (Issue #203)**: Integrate Ollama and build a cloud-fallback router.

## Infrastructure Notes (carried forward)
- **Observability columns are fail-safe**: `_write_obs_status()` in `scheduler.py` uses a SAVEPOINT per write; if columns are absent, rolls back the savepoint, sets `_has_obs_columns = False` (cached), and logs at DEBUG. Pre-migration environments are fully safe.
- **HealthChecker is backward-compatible**: Column check via `information_schema.columns`; if obs columns absent, returns `last_status/last_error/intent = None` for every process dict. No schema changes needed at read time.
- **related_bookmarks is fail-open**: If `_enrich_bookmarks_for_narrator` raises for any reason (no bookmarks file, parse error, etc.), `get_narrator_context` catches the exception, logs a warning, and returns `related_bookmarks: []`. Safe to call anywhere.
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
