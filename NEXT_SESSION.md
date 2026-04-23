# Next Session: BudgetGovernor Python-native WASM port (Phase 2) or HCAT Sandbox Dockerfile

## Current Status (2026-04-23, post-session #35)
- **ReviewPump Python-native WASM POC COMPLETE**: `poc/wasm/review-pump-py/` — zero-rewrite migration path fully validated. 34 pytest tests, parity with Rust review-pump. `LOGIC_VACUUMING_CANDIDATES.md` updated (Phase 1.7).
- **ask_mecris RAG pipeline COMPLETE**: BM25 retrieval (session #33) + LLM generation step (session #34). `ask_mecris(query)` returns `{query, result_count, answer, results, note}`. `answer` is synthesized by `claude-haiku-4-5-20251001` when `ANTHROPIC_API_KEY` is set; `None` (fail-open) otherwise.
- **39 tests pass** in `tests/test_ask_mecris.py`. **34 tests pass** in `tests/test_review_pump_py_component.py`.
- **WASM Migration Phase 2**: BudgetGovernor Python-native port is the natural next step per LOGIC_VACUUMING_CANDIDATES.md.
- **Ghost Archivist loop complete**: Token Bank (session #29) + Post-Mortem Generator (session #30). Blocked on human applying migrate_v7 to Neon.

## Verified This Session
- [x] **ReviewPump Python-native WASM POC (yebyen/mecris#261)**: `poc/wasm/review-pump-py/app.py` — componentize-py HTTP trigger pattern. `calculate_target`, `get_status`, `_parse_request`, `_json_ok`, `_error_json` all importable without WASM runtime. 34/34 tests green (`tests/test_review_pump_py_component.py`). Committed `ca90259`.
- [x] **module collision fix**: Used `importlib.util.spec_from_file_location` to load `review_pump_py_app` by absolute path, preventing `sys.modules['app']` collision with `test_arabic_skip_counter_component.py`.
- [x] **LOGIC_VACUUMING_CANDIDATES.md Phase 1.7**: Migration sequence updated to record all completed phases (0, 1, 1.5b, 1.6, 1.7).

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Apply migrate_v7 to production Neon**: `token_bank` and `autonomous_turns` tables. Run `python scripts/migrate_v7_autonomous_tracking.py`.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure (`ExceptionInInitializerError` at line 35) — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Renovate app install**: `renovate.json` is committed but Renovate bot must be installed on the GitHub repo to take effect. Install from https://github.com/apps/renovate.
- [ ] **Verify ask_mecris answer quality**: With a real `ANTHROPIC_API_KEY` in the MCP server env, call `ask_mecris("what is mecris?")` and confirm the `answer` field is prose (not None).
- [ ] **Verify poc/wasm/review-pump-py/ builds**: Run `pip install -r requirements.txt && spin py2wasm app -o review-pump-py.wasm` in a `spin`-enabled environment to confirm the binary compiles.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **BudgetGovernor Python-native WASM (Phase 2)**: `services/budget_governor.py` → `poc/wasm/budget-governor-py/` or `mecris-go-spin/budget-governor-py/`. Replace `File I/O` with Spin KV, `requests` with `spin_sdk` outbound HTTP, `os.getenv` with Spin variables. Core envelope logic is pure Python — portable with componentize-py. Use `IncomingHandler` pattern from `arabic-skip-counter` (Phase 1.6). Pattern established; now apply it to BudgetGovernor.
- [ ] **The Holy Grail: Python-Native WASM Migration (Issue #157)**: Remaining deliverable: wire `poc/wasm/review-pump-py/` into `spin.toml` as an HTTP route (`/internal/review-pump-status-py`) alongside the Rust version. Demonstrate side-by-side parity.
- [ ] **Dual-Widget "Debt vs. Flow" UI (Issue #160)**: Android UI Epic. Build a secondary gauge indicator to visualize long-term debt vs daily flow.
- [ ] **Port Twilio to WASM Brain (Issue #167)**: Move SMS/WhatsApp dispatch logic from Python/boris-fiona-walker into the `sync-service` Rust module.
- [ ] **Rust Reminder Engine (Issue #169)**: Implement the 2000-step threshold, sleep window heuristics, and weather checks natively in Rust.
- [ ] **Contextual Awareness: Chrome Bookmarks (Issue #201)**: Build a local Chrome bookmarks parser and MCP endpoint.
- [ ] **Local Inference Pipeline (Issue #203)**: Integrate Ollama and build a cloud-fallback router. (ask_mecris already uses Anthropic as interim — this would let it run offline.)
- [ ] **Autonomous Security: JIT Secret Manager (Issue #204)**: Implement secure credential retrieval for headless `gemini --yolo` turns.
- [ ] **AI Framework Evaluation (Issue #205)**: Formalize evaluation matrix and run POC tests.
- [ ] **Headless Loopback for gh copilot (Issue #206)**: Subprocess wrapper for `gh copilot`.
- [ ] **Semantic Search: Bookmark Embeddings (Issue #208)**: Generate vector index for Chrome bookmarks.
- [ ] **HCAT Sandbox Dockerfile (Issue #210)**: Create a hardened, SHA-pinned Dockerfile for executing autonomous agents securely.
- [ ] **Human Yield Presence Detection (Issue #211)**: Add logic to detect human workstation activity and manage the `presence.lock` safely.
- [ ] **Observability: Log Local Notifications (Issue #213)**: Implement remote logging for local Android notifications to provide a complete accountability audit trail.
- [ ] **Budget Governor: WASM Port (Issue #214)**: Port the 5%/5% spend envelope logic from Python to Rust to ensure consistent routing recommendations in the cloud.

## Infrastructure Notes (carried forward)
- **poc/wasm/ pattern**: Use `importlib.util.spec_from_file_location("unique_name", path)` when loading WASM component `app.py` files in tests to avoid `sys.modules['app']` collision.
- **componentize-py class naming**: Function-export world → `class WitWorld`. HTTP trigger world → `class IncomingHandler(spin_sdk.http.IncomingHandler)`. See `LOGIC_VACUUMING_CANDIDATES.md` for full details.
- **ask_mecris corpus**: `_rag_retriever` is module-level in `mcp_server.py`. Corpus loaded lazily on first `ask_mecris` call. Force re-index: `_rag_retriever.reset()`. Covers docs/ (95 files) + attic/session-chunks/ (17 files) = 112 documents.
- **ask_mecris result shape**: `{query, result_count, answer, results, note}`. `answer` is `Optional[str]` — prose when `ANTHROPIC_API_KEY` is set and API succeeds, `None` otherwise. `results` always present (raw BM25 chunks).
- **rag_generator model**: `claude-haiku-4-5-20251001` by default. Override via `model=` kwarg if needed.
- **RAG front-matter**: `python scripts/add_docs_frontmatter.py` — stamps docs with YAML. Idempotent. `--force` overwrites existing. All 95 docs already stamped.
- **RAG chunk files**: `attic/session-chunks/YYYY-MM-DD.md` — YAML front-matter with `date`, `primary_activity`, `entry_count`, `source`. Regenerate with `python scripts/chunk_session_logs.py`.
- **Doc graph verifier**: `python scripts/verify_docs_graph.py [--json]` — scan `docs/` for broken/orphaned links. Zero broken links currently.
- **Post-Mortem Generator**: `PostMortemGenerator` in `ghost/post_mortem.py` — fail-open, returns None without NEON_DB_URL. Use `PostMortemGenerator(db_url=...).run(user_id)` to generate reports.
- **Token Bank**: `TokenBankService` is fail-open — without `NEON_DB_URL`, `check_and_debit` returns 0 and logs a warning. Safe to import without a live DB.
- **smart_nag integration complete**: `ReminderService` receives `walk_history_provider=get_walk_history` (mcp_server.py). SQL: `SELECT start_time FROM walk_inferences WHERE user_id = %s AND start_time >= %s ORDER BY start_time ASC` (last 30 days).
- **mecris pulse**: `render_pulse(context)` is a pure function — safe to call with any dict. `run_pulse(user_id)` is the async entrypoint importing `get_narrator_context` at call time (deferred import avoids circular dependency at module load).
- **DelayedNagWorker time guards**: Arabic 08:00–20:00; Walk 08:00–20:00 (fixed session #25); Sovereign Fallback 08:00–20:00 (fixed session #25); GREEK 17:00–22:30.
- **phone_verified column**: `ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE` — Apply migrate_v6 to production Neon.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **Moussaka Exception**: `last_greek_nag_timestamp` → 1.5h cooldown. All others: 4h.
- **MECRIS_MODE=standalone** bypasses JWKS; `MECRIS_MODE=cloud` enforces RSA verification.
