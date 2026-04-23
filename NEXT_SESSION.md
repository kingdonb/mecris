# Next Session: Conversational RAG Generation Layer (kingdonb/mecris#207) or WASM Migration POC (kingdonb/mecris#157)

## Current Status (2026-04-23, post-session #33)
- **ask_mecris BM25 retrieval COMPLETE**: `services/rag_retriever.py` (pure-Python BM25) + `ask_mecris` MCP tool registered in `mcp_server.py`. 30 tests pass. Committed `f7786cf`. Plan yebyen/mecris#259 closed.
- **RAG query layer is retrieval-only**: No generation (no LLM call in ask_mecris). Returns top-5 ranked chunks with metadata — the caller uses them as context. Full conversational RAG (generation step) blocked on Local Inference Pipeline (kingdonb/mecris#203) or similar.
- **RAG Foundation still COMPLETE**: All 95 docs/ files have YAML front-matter; 17 session chunks in `attic/session-chunks/`; doc graph verifier shows 0 broken links.
- **Ghost Archivist loop complete**: Token Bank (session #29) + Post-Mortem Generator (session #30). Blocked on human applying migrate_v7 to Neon.
- **WASM Migration POC (kingdonb/mecris#157)** remains highest-priority architectural item on roadmap.

## Verified This Session
- [x] **ask_mecris MCP tool (yebyen/mecris#259)**: `services/rag_retriever.py` — pure-Python BM25 with lazy corpus loading, front-matter parsing, doc + session-chunk loaders. `ask_mecris(query)` MCP tool registered in `mcp_server.py`. 30 unit tests pass. Committed `f7786cf`.
- [x] **Corpus is indexed**: `RAGRetriever` loads all 95 `docs/*.md` + 17 `attic/session-chunks/*.md` on first retrieve call. Idempotent — re-index via `_rag_retriever.reset()`.
- [x] **Empty query guard**: Returns `{result_count: 0, results: []}` without hitting the corpus.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Apply migrate_v7 to production Neon**: `token_bank` and `autonomous_turns` tables. Run `python scripts/migrate_v7_autonomous_tracking.py`.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure (`ExceptionInInitializerError` at line 35) — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Renovate app install**: `renovate.json` is committed but Renovate bot must be installed on the GitHub repo to take effect. Install from https://github.com/apps/renovate.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Conversational RAG: generation step (Issue #207)**: `ask_mecris` retrieval is done. Next: wire a generation call (Ollama / cloud LLM) to synthesize retrieved chunks into a natural language answer. Blocked on Local Inference Pipeline (#203) unless using a direct Anthropic SDK call as interim.
- [ ] **The Holy Grail: Python-Native WASM Migration (Issue #157)**: Research `componentize-py` and build a POC WASM component derived directly from Python logic.
- [ ] **Dual-Widget "Debt vs. Flow" UI (Issue #160)**: Android UI Epic. Build a secondary gauge indicator to visualize long-term debt vs daily flow.
- [ ] **Port Twilio to WASM Brain (Issue #167)**: Move SMS/WhatsApp dispatch logic from Python/boris-fiona-walker into the `sync-service` Rust module.
- [ ] **Rust Reminder Engine (Issue #169)**: Implement the 2000-step threshold, sleep window heuristics, and weather checks natively in Rust.
- [ ] **Contextual Awareness: Chrome Bookmarks (Issue #201)**: Build a local Chrome bookmarks parser and MCP endpoint.
- [ ] **Local Inference Pipeline (Issue #203)**: Integrate Ollama and build a cloud-fallback router.
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
- **ask_mecris result shape**: `{source, title, description, date, type, snippet}` per result. `type` is `"doc"` or `"session"`.
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
