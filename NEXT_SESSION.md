# Next Session: Pick next beta.3 feature from backlog

## Current Status (2026-04-22, post-session #28)
- **renovate.json complete**: Centralized Renovate configuration committed (`fada2e6`). Covers Python (pep621), Rust (cargo), Android/Gradle (gradle + gradle-wrapper), and Web/npm. Weekly schedule (Monday AM ET), grouped PRs per ecosystem, major bumps labeled `major-update`. Closes kingdonb/mecris#199.
- **mecris pulse complete**: `cli/pulse.py` delivers a `rich`-powered terminal dashboard via `mecris pulse`. Commit `c367c98`. Closes kingdonb/mecris#215.
- **18 tests green**: All `tests/test_pulse.py` tests pass (helper color logic, mock context structure, render_pulse smoke tests — 6 render variants tested).
- **CLI wired**: `mecris pulse` subcommand registered in `cli/main.py`, dispatches to `run_pulse()` which calls `get_narrator_context` from mcp_server.
- **v0.0.1-beta.3 dev cycle active**: Large backlog of features awaiting bot work.

## Verified This Session
- [x] **renovate.json (yebyen/mecris#253)**: Created covering pep621, cargo, gradle, npm. JSON valid. Committed `fada2e6`. Closes kingdonb/mecris#199.
- [x] **mecris pulse CLI dashboard (yebyen/mecris#251)**: `cli/pulse.py` implemented, `mecris pulse` wired, 18 tests green. Commit `c367c98`.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure (`ExceptionInInitializerError` at line 35) — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.
- [ ] **Renovate app install**: `renovate.json` is committed but Renovate bot must be installed on the GitHub repo to take effect. Install from https://github.com/apps/renovate.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **The Holy Grail: Python-Native WASM Migration (Issue #157)**: Research `componentize-py` and build a POC WASM component derived directly from Python logic.
- [ ] **Dual-Widget "Debt vs. Flow" UI (Issue #160)**: Android UI Epic. Build a secondary gauge indicator to visualize long-term debt vs daily flow.
- [ ] **Port Twilio to WASM Brain (Issue #167)**: Move SMS/WhatsApp dispatch logic from Python/boris-fiona-walker into the `sync-service` Rust module.
- [ ] **Rust Reminder Engine (Issue #169)**: Implement the 2000-step threshold, sleep window heuristics, and weather checks natively in Rust.
- [ ] **Contextual Awareness: Chrome Bookmarks (Issue #201)**: Build a local Chrome bookmarks parser and MCP endpoint.
- [ ] **RAG Foundation: Documentation Graph (Issue #202)**: Standardize doc front-matter and implement automated link/graph verification.
- [ ] **Local Inference Pipeline (Issue #203)**: Integrate Ollama and build a cloud-fallback router.
- [ ] **Autonomous Security: JIT Secret Manager (Issue #204)**: Implement secure credential retrieval for headless `gemini --yolo` turns.
- [ ] **AI Framework Evaluation (Issue #205)**: Formalize evaluation matrix and run POC tests.
- [ ] **Headless Loopback for gh copilot (Issue #206)**: Subprocess wrapper for `gh copilot`.
- [ ] **Conversational RAG (Issue #207)**: Implement `ask_mecris` MCP query interface.
- [ ] **Semantic Search: Bookmark Embeddings (Issue #208)**: Generate vector index for Chrome bookmarks.
- [ ] **Agent Constraints: Token Bank (Issue #209)**: Update Neon schema to track and rate-limit autonomous ghost sessions.
- [ ] **HCAT Sandbox Dockerfile (Issue #210)**: Create a hardened, SHA-pinned Dockerfile for executing autonomous agents securely.
- [ ] **Human Yield Presence Detection (Issue #211)**: Add logic to detect human workstation activity and manage the `presence.lock` safely.
- [ ] **Observability: Log Local Notifications (Issue #213)**: Implement remote logging for local Android notifications to provide a complete accountability audit trail.
- [ ] **Budget Governor: WASM Port (Issue #214)**: Port the 5%/5% spend envelope logic from Python to Rust to ensure consistent routing recommendations in the cloud.
- [ ] **Autonomous Post-Mortem Generator (Issue #216)**: Enable the Ghost Archivist to detect failed turns and autonomously draft analysis reports in the attic.

## Infrastructure Notes (carried forward)
- **smart_nag integration complete**: `ReminderService` receives `walk_history_provider=get_walk_history` (mcp_server.py). SQL: `SELECT start_time FROM walk_inferences WHERE user_id = %s AND start_time >= %s ORDER BY start_time ASC` (last 30 days).
- **mecris pulse**: `render_pulse(context)` is a pure function — safe to call with any dict. `run_pulse(user_id)` is the async entrypoint importing `get_narrator_context` at call time (deferred import avoids circular dependency at module load).
- **DelayedNagWorker time guards**: Arabic 08:00–20:00; Walk 08:00–20:00 (fixed session #25); Sovereign Fallback 08:00–20:00 (fixed session #25); GREEK 17:00–22:30.
- **phone_verified column**: `ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE` — Apply migrate_v6 to production Neon.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **Moussaka Exception**: `last_greek_nag_timestamp` → 1.5h cooldown. All others: 4h.
- **MECRIS_MODE=standalone** bypasses JWKS; `MECRIS_MODE=cloud` enforces RSA verification.
