# Next Session: WASM Migration POC (kingdonb/mecris#157) or RAG Foundation completion (kingdonb/mecris#202)

## Current Status (2026-04-23, post-session #31)
- **RAG Foundation scripts complete**: `scripts/verify_docs_graph.py` (doc link graph verifier) and `scripts/chunk_session_logs.py` (session log chunker) implemented and committed `6e64e12`. Closes partial scope of kingdonb/mecris#202.
- **Session chunks generated**: 74 session entries across 17 dates written to `attic/session-chunks/` with YAML front-matter. Ready for future vector indexing.
- **Doc graph result**: 95 docs scanned, 0 broken links, 91 orphaned docs (expected — most docs are standalone planning documents, not cross-linked).
- **Remaining #202 scope**: Front-matter standardization on docs/ files (70+ files) not done — large mechanical task for a future session.
- **Full Ghost Archivist loop exists**: Token Bank (session #29) + Post-Mortem Generator (session #30) complete. Self-healing cycle structurally complete.
- **Blocked on prod**: Post-Mortem Generator and Token Bank require human to apply migrate_v7 to Neon.

## Verified This Session
- [x] **RAG Foundation scripts (yebyen/mecris#256)**: `scripts/verify_docs_graph.py` + `scripts/chunk_session_logs.py`. Both execute without errors. 17 chunk files + PREAMBLE in `attic/session-chunks/`. Committed `6e64e12`.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Apply migrate_v7 to production Neon**: `token_bank` and `autonomous_turns` tables. Run `python scripts/migrate_v7_autonomous_tracking.py`.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure (`ExceptionInInitializerError` at line 35) — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Renovate app install**: `renovate.json` is committed but Renovate bot must be installed on the GitHub repo to take effect. Install from https://github.com/apps/renovate.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **RAG Foundation: YAML front-matter on docs/ (Issue #202 remaining)**: Add YAML metadata blocks to all 70+ files in `docs/`. Large mechanical task — consider scripting it.
- [ ] **The Holy Grail: Python-Native WASM Migration (Issue #157)**: Research `componentize-py` and build a POC WASM component derived directly from Python logic.
- [ ] **Dual-Widget "Debt vs. Flow" UI (Issue #160)**: Android UI Epic. Build a secondary gauge indicator to visualize long-term debt vs daily flow.
- [ ] **Port Twilio to WASM Brain (Issue #167)**: Move SMS/WhatsApp dispatch logic from Python/boris-fiona-walker into the `sync-service` Rust module.
- [ ] **Rust Reminder Engine (Issue #169)**: Implement the 2000-step threshold, sleep window heuristics, and weather checks natively in Rust.
- [ ] **Contextual Awareness: Chrome Bookmarks (Issue #201)**: Build a local Chrome bookmarks parser and MCP endpoint.
- [ ] **Local Inference Pipeline (Issue #203)**: Integrate Ollama and build a cloud-fallback router.
- [ ] **Autonomous Security: JIT Secret Manager (Issue #204)**: Implement secure credential retrieval for headless `gemini --yolo` turns.
- [ ] **AI Framework Evaluation (Issue #205)**: Formalize evaluation matrix and run POC tests.
- [ ] **Headless Loopback for gh copilot (Issue #206)**: Subprocess wrapper for `gh copilot`.
- [ ] **Conversational RAG (Issue #207)**: Implement `ask_mecris` MCP query interface.
- [ ] **Semantic Search: Bookmark Embeddings (Issue #208)**: Generate vector index for Chrome bookmarks.
- [ ] **HCAT Sandbox Dockerfile (Issue #210)**: Create a hardened, SHA-pinned Dockerfile for executing autonomous agents securely.
- [ ] **Human Yield Presence Detection (Issue #211)**: Add logic to detect human workstation activity and manage the `presence.lock` safely.
- [ ] **Observability: Log Local Notifications (Issue #213)**: Implement remote logging for local Android notifications to provide a complete accountability audit trail.
- [ ] **Budget Governor: WASM Port (Issue #214)**: Port the 5%/5% spend envelope logic from Python to Rust to ensure consistent routing recommendations in the cloud.

## Infrastructure Notes (carried forward)
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
