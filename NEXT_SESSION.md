# Next Session: Pick next feature from beta.3 backlog (kingdonb/mecris#201–#208)

## Current Status (2026-04-21, post-session-#23)
- **PR #198 merged**: All 9 commits (obsidian, headless, android UI) are now in `main`.
- **v0.0.1-beta.3 tagged**: Version bumped by kingdonb; beta.3 dev cycle underway.
- **smart_nag implemented**: `services/smart_nag.py` + 17 unit tests, committed `1883cf6` (session #23).
- **Bot productivity high**: Deep backlog populated; test coverage growing each session.

## Verified This Session
- [x] **Smart Nagging: Success Patterns (kingdonb/mecris#200)**: `services/smart_nag.py` with
  `evaluate_nag()`, `success_probability()`, `find_peak_success_window()`.
  17/17 tests green. Commit `1883cf6`.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure (`ExceptionInInitializerError` at line 35) — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Open next feature work**: Pick from the high-depth backlog below.
- [ ] **Fix Overly Ambitious Morning Notifications (Issue #212)**: Add strict 8 AM start guards to `DelayedNagWorker.kt` to prevent pre-sunrise walk reminders.
- [ ] **The Holy Grail: Python-Native WASM Migration (Issue #157)**: Research `componentize-py` and build a POC WASM component derived directly from Python logic.
- [ ] **Dual-Widget "Debt vs. Flow" UI (Issue #160)**: Android UI Epic. Build a secondary gauge indicator to visualize long-term debt vs daily flow (building on #194/#195).
- [ ] **Port Twilio to WASM Brain (Issue #167)**: Move SMS/WhatsApp dispatch logic from Python/boris-fiona-walker directly into the `sync-service` Rust module.
- [ ] **Rust Reminder Engine (Issue #169)**: Implement the 2000-step threshold, sleep window heuristics, and weather checks natively in Rust for the background trigger.
- [ ] **Implement Renovate Configuration (Issue #199)**: Create a centralized `renovate.json` to manage dependencies across all modules (Python, Rust, Android, Web).
- [ ] **Smart Nagging: Success Patterns (Issue #200)**: Implement probability-based nag suppression in `services/smart_nag.py` using historical walk data.
- [ ] **Contextual Awareness: Chrome Bookmarks (Issue #201)**: Build a local Chrome bookmarks parser and MCP endpoint to surface relevant research in the Narrator context.
- [ ] **RAG Foundation: Documentation Graph (Issue #202)**: Standardize doc front-matter and implement automated link/graph verification to prepare for vector indexing.
- [ ] **Local Inference Pipeline (Issue #203)**: Integrate Ollama and build a cloud-fallback router to manage RAG costs.
- [ ] **Autonomous Security: JIT Secret Manager (Issue #204)**: Implement secure credential retrieval and passing for headless `gemini --yolo` turns.
- [ ] **AI Framework Evaluation (Issue #205)**: Formalize evaluation matrix and run proof-of-concept tests for alternatives to Claude Code.
- [ ] **Headless Loopback for gh copilot (Issue #206)**: Subprocess wrapper for `gh copilot` to allow autonomous shell scripting assistance.
- [ ] **Conversational RAG (Issue #207)**: Implement `ask_mecris` MCP query interface using Ollama router and local documentation index.
- [ ] **Semantic Search: Bookmark Embeddings (Issue #208)**: Generate vector index for Chrome bookmarks and surface results in Narrator context.
- [ ] **Agent Constraints: Token Bank (Issue #209)**: Update Neon schema to track and rate-limit autonomous ghost sessions.
- [ ] **HCAT Sandbox Dockerfile (Issue #210)**: Create a hardened, SHA-pinned Dockerfile for executing autonomous agents securely.
- [ ] **Human Yield Presence Detection (Issue #211)**: Add logic to detect human workstation activity and manage the `presence.lock` safely.

## New Features Landed in beta.2 dev cycle (since beta.1 baseline `90a569e`)

- **fix(android): Number/Double division type error in ReviewPumpWidget progress bar** (`a8dd56f`): `remainingToday.toDouble()` at line 1160 — resolves compile error from `Number` type inference.
- **feat(android): Majesty Rings + all_clear state to MomentumVisualizer** (`96a3fb5`): `MomentumOrbState` enum, Gold/Green/Red states, animated expanding rings.
- **feat(android): REMAINING TODAY counter backport** (`e30cda5`): `LanguageStatDto` gains `target_flow_rate`, `absolute_target`, `goal_met`; `ReviewPumpWidget` uses server value.
- **feat(ghost): HeadlessLoopback subprocess wrapper** (`0e50bb4`): `ghost/headless_loopback.py` — spawns `gemini --yolo`, captures stdout/stderr, SIGKILL timeout.
- **feat(obsidian): alternate checkbox styles in todo parser** (`ebe3d30`): Broaden regex to `[^\[\]]`; expose raw `status` char.
- **feat(security): achieve SLSA Build Level 2** (`293b822`): Signed provenance via `actions/attest-build-provenance@v2`.
- **chore(release): bump version to 0.0.1-beta.2** (`34d8582`): Dev cycle baseline set.

## Version Baseline (v0.0.1-beta.2)
- **Android**: 1.1.6-beta.2
- **Spin sync-service**: 0.3.1-beta.2
- **Python MCP**: 0.5.1-beta.2
- **Suite**: 0.0.1-beta.2
- [ ] **Implement Renovate Configuration (kingdonb/mecris#199)**: Create a centralized `renovate.json` to manage dependencies across all modules (Python, Rust, Android, Web).
- [ ] **Contextual Awareness: Chrome Bookmarks (kingdonb/mecris#201)**: Build a local Chrome bookmarks parser and MCP endpoint to surface relevant research in the Narrator context.
- [ ] **RAG Foundation: Documentation Graph (kingdonb/mecris#202)**: Standardize doc front-matter and implement automated link/graph verification to prepare for vector indexing.
- [ ] **Local Inference Pipeline (kingdonb/mecris#203)**: Integrate Ollama and build a cloud-fallback router to manage RAG costs.
- [ ] **Autonomous Security: JIT Secret Manager (kingdonb/mecris#204)**: Implement secure credential retrieval and passing for headless `gemini --yolo` turns.
- [ ] **AI Framework Evaluation (kingdonb/mecris#205)**: Formalize evaluation matrix and run proof-of-concept tests for alternatives to Claude Code.
- [ ] **Headless Loopback for gh copilot (kingdonb/mecris#206)**: Subprocess wrapper for `gh copilot` to allow autonomous shell scripting assistance.
- [ ] **Conversational RAG (kingdonb/mecris#207)**: Implement `ask_mecris` MCP query interface using Ollama router and local documentation index.
- [ ] **Semantic Search: Bookmark Embeddings (kingdonb/mecris#208)**: Generate vector index for Chrome bookmarks and surface results in Narrator context.

## Infrastructure Notes (carried forward)
- **phone_verified column**: `ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE` — Apply migrate_v6 to production Neon.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **DelayedNagWorker time guards**: Arabic 08:00–20:00; Walk 08:00+; GREEK 17:00–22:30.
- **Moussaka Exception**: `last_greek_nag_timestamp` → 1.5h cooldown. All others: 4h.
- **MECRIS_MODE=standalone** bypasses JWKS; `MECRIS_MODE=cloud` enforces RSA verification.
- **smart_nag integration note**: `services/smart_nag.py` is a pure-function library; it needs a
  DB-backed `walk_history_provider` wired up in `reminder_service.py` or a scheduler task to
  actually suppress/escalate live nags. The math works; plumbing is the next step.
