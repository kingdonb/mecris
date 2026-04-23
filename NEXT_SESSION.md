# Next Session: Wire review-pump-py into spin.toml (Holy Grail #157) or HCAT Sandbox Dockerfile (#210)

## Current Status (2026-04-23, post-session #36)
- **BudgetGovernor Python-native WASM POC COMPLETE**: `poc/wasm/budget-governor-py/` — 61/61 tests green. `IncomingHandler` with 5 actions (status, check, record, recommend, gate). Spin KV for persistence; Spin variables for limits; `spin_sdk` outbound HTTP for Helix balance. Committed `4fd02ab`.
- **ReviewPump Python-native WASM POC COMPLETE**: `poc/wasm/review-pump-py/` — 34 tests, parity with Rust review-pump. `LOGIC_VACUUMING_CANDIDATES.md` updated (Phase 1.7).
- **ask_mecris RAG pipeline COMPLETE**: BM25 retrieval + LLM generation (claude-haiku-4-5-20251001). 39 tests pass.
- **Two WASM POCs validated**: The componentize-py + `IncomingHandler` pattern is now established for both ReviewPump and BudgetGovernor. The next step is wiring one into `spin.toml`.

## Verified This Session
- [x] **BudgetGovernor Python-native WASM POC (yebyen/mecris#262)**: `poc/wasm/budget-governor-py/app.py` — componentize-py HTTP trigger. 61/61 tests green (`tests/test_budget_governor_py_component.py`). Committed `4fd02ab`.
- [x] **5%/5% envelope logic portable**: `check_envelope`, `recommend_bucket`, `get_status`, `budget_gate`, `_calc_total_spent`, `_calc_window_spent` all importable without WASM runtime. Logic contract matches `services/budget_governor.py`.
- [x] **Spend log KV serialization**: `_load_spend_log_from_json`, `_dump_spend_log_to_json` round-trip verified in tests. Replaces file I/O from original `BudgetGovernor` class.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Apply migrate_v7 to production Neon**: `token_bank` and `autonomous_turns` tables. Run `python scripts/migrate_v7_autonomous_tracking.py`.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure (`ExceptionInInitializerError` at line 35) — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Renovate app install**: `renovate.json` is committed but Renovate bot must be installed on the GitHub repo to take effect. Install from https://github.com/apps/renovate.
- [ ] **Verify ask_mecris answer quality**: With a real `ANTHROPIC_API_KEY` in the MCP server env, call `ask_mecris("what is mecris?")` and confirm the `answer` field is prose (not None).
- [ ] **Verify poc/wasm/review-pump-py/ builds**: Run `pip install -r requirements.txt && spin py2wasm app -o review-pump-py.wasm` in a `spin`-enabled environment.
- [ ] **Verify poc/wasm/budget-governor-py/ builds**: Run `pip install -r requirements.txt && spin py2wasm app -o budget-governor-py.wasm` in a `spin`-enabled environment.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **The Holy Grail: Python-Native WASM Migration (Issue #157)**: Wire `poc/wasm/review-pump-py/` into `spin.toml` as an HTTP route (`/internal/review-pump-status-py`) alongside the Rust version. Demonstrate side-by-side parity. Pattern is established — just needs the `spin.toml` stanza and CI wiring.
- [ ] **Wire BudgetGovernor WASM into spin.toml**: Add `poc/wasm/budget-governor-py/` as `/internal/budget-governor-py` route. Second integration target after ReviewPump.
- [ ] **HCAT Sandbox Dockerfile (Issue #210)**: Create a hardened, SHA-pinned Dockerfile for executing autonomous agents securely.
- [ ] **Dual-Widget "Debt vs. Flow" UI (Issue #160)**: Android UI Epic. Build a secondary gauge indicator to visualize long-term debt vs daily flow.
- [ ] **Port Twilio to WASM Brain (Issue #167)**: Move SMS/WhatsApp dispatch logic from Python/boris-fiona-walker into the `sync-service` Rust module.
- [ ] **Rust Reminder Engine (Issue #169)**: Implement the 2000-step threshold, sleep window heuristics, and weather checks natively in Rust.
- [ ] **Contextual Awareness: Chrome Bookmarks (Issue #201)**: Build a local Chrome bookmarks parser and MCP endpoint.
- [ ] **Local Inference Pipeline (Issue #203)**: Integrate Ollama and build a cloud-fallback router.
- [ ] **Autonomous Security: JIT Secret Manager (Issue #204)**: Implement secure credential retrieval for headless `gemini --yolo` turns.
- [ ] **AI Framework Evaluation (Issue #205)**: Formalize evaluation matrix and run POC tests.
- [ ] **Headless Loopback for gh copilot (Issue #206)**: Subprocess wrapper for `gh copilot`.
- [ ] **Semantic Search: Bookmark Embeddings (Issue #208)**: Generate vector index for Chrome bookmarks.
- [ ] **Human Yield Presence Detection (Issue #211)**: Add logic to detect human workstation activity and manage the `presence.lock` safely.
- [ ] **Observability: Log Local Notifications (Issue #213)**: Implement remote logging for local Android notifications.
- [ ] **Budget Governor: WASM Port (Issue #214)**: PARTIALLY COMPLETE — POC in `poc/wasm/budget-governor-py/`. Remaining: wire into `spin.toml`, add KV schema init, add Helix balance variable config in Fermyon.

## Infrastructure Notes (carried forward)
- **poc/wasm/ pattern**: Use `importlib.util.spec_from_file_location("unique_name", path)` when loading WASM component `app.py` files in tests to avoid `sys.modules['app']` collision.
- **componentize-py class naming**: Function-export world → `class WitWorld`. HTTP trigger world → `class IncomingHandler(spin_sdk.http.IncomingHandler)`. See `LOGIC_VACUUMING_CANDIDATES.md` for full details.
- **BudgetGovernor WASM action API**: POST `/internal/budget-governor` with `{"action": "status"|"check"|"record"|"recommend"|"gate", "bucket": str, "cost": float}`.
- **ask_mecris corpus**: `_rag_retriever` is module-level in `mcp_server.py`. Corpus loaded lazily on first `ask_mecris` call. Force re-index: `_rag_retriever.reset()`. Covers docs/ (95 files) + attic/session-chunks/ (17 files) = 112 documents.
- **ask_mecris result shape**: `{query, result_count, answer, results, note}`. `answer` is `Optional[str]` — prose when `ANTHROPIC_API_KEY` is set and API succeeds, `None` otherwise.
- **rag_generator model**: `claude-haiku-4-5-20251001` by default. Override via `model=` kwarg if needed.
- **smart_nag integration complete**: `ReminderService` receives `walk_history_provider=get_walk_history` (mcp_server.py). SQL: `SELECT start_time FROM walk_inferences WHERE user_id = %s AND start_time >= %s ORDER BY start_time ASC` (last 30 days).
- **phone_verified column**: `ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE` — Apply migrate_v6 to production Neon.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **Moussaka Exception**: `last_greek_nag_timestamp` → 1.5h cooldown. All others: 4h.
- **MECRIS_MODE=standalone** bypasses JWKS; `MECRIS_MODE=cloud` enforces RSA verification.
- **DelayedNagWorker time guards**: Arabic 08:00–20:00; Walk 08:00–20:00; Sovereign Fallback 08:00–20:00; GREEK 17:00–22:30.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning. Safe to import without a live DB.
- **Post-Mortem Generator**: `PostMortemGenerator` in `ghost/post_mortem.py` — fail-open, returns None without NEON_DB_URL.
- **mecris pulse**: `render_pulse(context)` is a pure function — safe to call with any dict. `run_pulse(user_id)` is the async entrypoint importing `get_narrator_context` at call time.
