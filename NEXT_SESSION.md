# Next Session: WASM Migration POC (kingdonb/mecris#157) or Conversational RAG hardening

## Current Status (2026-04-23, post-session #34)
- **ask_mecris RAG pipeline COMPLETE**: BM25 retrieval (session #33) + LLM generation step (session #34). `ask_mecris(query)` now returns `{query, result_count, answer, results, note}`. `answer` is a prose string synthesized by `claude-haiku-4-5-20251001` when `ANTHROPIC_API_KEY` is set; `None` (fail-open) otherwise.
- **Generation is fail-open**: `services/rag_generator.py` — returns `None` on missing API key, missing SDK, or API error. No crashing the MCP server if Anthropic is unreachable.
- **39 tests pass** in `tests/test_ask_mecris.py` (30 retrieval + 9 generation). Committed `3a32853`.
- **WASM Migration POC (kingdonb/mecris#157)** remains highest-priority architectural item on roadmap.
- **Ghost Archivist loop complete**: Token Bank (session #29) + Post-Mortem Generator (session #30). Blocked on human applying migrate_v7 to Neon.

## Verified This Session
- [x] **ask_mecris generation step (yebyen/mecris#260)**: `services/rag_generator.py` — module-level `_anthropic_lib` import with try/except (patchable). `generate_answer(query, chunks, model)` builds numbered context block and calls `claude-haiku-4-5-20251001`. 9 tests: `_build_context`, fail-open (no key, empty chunks), mocked success, mocked API failure, model pass-through. 39/39 tests green.
- [x] **ask_mecris answer field**: `mcp_server.py` returns `"answer": answer` alongside raw BM25 chunks. Transparent fallback — caller sees `None` when generation is skipped.
- [x] **anthropic>=0.25.0 in requirements.txt**: Dependency added; installed via uv in CI build.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Apply migrate_v7 to production Neon**: `token_bank` and `autonomous_turns` tables. Run `python scripts/migrate_v7_autonomous_tracking.py`.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure (`ExceptionInInitializerError` at line 35) — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Renovate app install**: `renovate.json` is committed but Renovate bot must be installed on the GitHub repo to take effect. Install from https://github.com/apps/renovate.
- [ ] **Verify ask_mecris answer quality**: With a real `ANTHROPIC_API_KEY` in the MCP server env, call `ask_mecris("what is mecris?")` and confirm the `answer` field is prose (not None).

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **The Holy Grail: Python-Native WASM Migration (Issue #157)**: Research `componentize-py` and build a POC WASM component derived directly from Python logic. Highest architectural priority.
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
