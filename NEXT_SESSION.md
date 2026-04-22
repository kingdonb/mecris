# Next Session: Implement DB-backed walk_history_provider OR pick next beta.3 feature

## Current Status (2026-04-22, post-session #25)
- **quiet-hours guards standardized**: `DelayedNagWorker.kt` Walk branch now has `localHour >= 8 && localHour < 20` (was missing upper bound); Sovereign Fallback now has a full time guard (was completely unguarded). Commit `73fe632`. Closes kingdonb/mecris#212.
- **smart_nag fully integrated**: `ReminderService.check_reminder_needed()` calls `evaluate_nag()` with a `walk_history_provider`. Interface contract established; 61/61 tests green. Commit `dcc6496`.
- **Interface contract defined**: `walk_history_provider` is `async (user_id) -> List[datetime]` — next step is a real Neon DB query implementation.
- **catch-up nag live**: `walk_reminder_catchup` (tier 2, no template) fires outside the standard window when peak window has passed without activity.
- **Suppression live**: Walk reminder suppressed inside window when `success_probability > 0.70`.
- **v0.0.1-beta.3 dev cycle active**: Large backlog of features awaiting bot work.

## Verified This Session
- [x] **quiet-hours guards (yebyen/mecris#249)**: Walk branch `localHour < 20` upper bound added; Sovereign Fallback `localHourFallback >= 8 && localHourFallback < 20` guard added. 61/61 tests green. Commit `73fe632`.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure (`ExceptionInInitializerError` at line 35) — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **DB-backed walk_history_provider**: Implement a real Neon DB query that returns `List[datetime]` of recent walk start times, wired into the scheduler/worker that calls `check_reminder_needed()`. The interface is defined; this is the next plumbing step.
- [ ] **The Holy Grail: Python-Native WASM Migration (Issue #157)**: Research `componentize-py` and build a POC WASM component derived directly from Python logic.
- [ ] **Dual-Widget "Debt vs. Flow" UI (Issue #160)**: Android UI Epic. Build a secondary gauge indicator to visualize long-term debt vs daily flow.
- [ ] **Port Twilio to WASM Brain (Issue #167)**: Move SMS/WhatsApp dispatch logic from Python/boris-fiona-walker into the `sync-service` Rust module.
- [ ] **Rust Reminder Engine (Issue #169)**: Implement the 2000-step threshold, sleep window heuristics, and weather checks natively in Rust.
- [ ] **Implement Renovate Configuration (Issue #199)**: Create a centralized `renovate.json` to manage dependencies across all modules.
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

## Infrastructure Notes (carried forward)
- **smart_nag integration note**: `ReminderService` now accepts `walk_history_provider`. The worker/scheduler that instantiates `ReminderService` must pass a real DB-backed provider. The interface: `async (user_id: str | None) -> List[datetime]` — returns walk start datetimes for the last 30 days.
- **DelayedNagWorker time guards**: Arabic 08:00–20:00; Walk 08:00–20:00 (fixed this session); Sovereign Fallback 08:00–20:00 (fixed this session); GREEK 17:00–22:30.
- **phone_verified column**: `ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE` — Apply migrate_v6 to production Neon.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **Moussaka Exception**: `last_greek_nag_timestamp` → 1.5h cooldown. All others: 4h.
- **MECRIS_MODE=standalone** bypasses JWKS; `MECRIS_MODE=cloud` enforces RSA verification.
