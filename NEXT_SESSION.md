# Next Session: Feature momentum after PR #198 merge

## Current Status (2026-04-21, post-PR-merge)
- **PR #198 merged**: All 9 commits (obsidian, headless, android UI) are now in `main`.
- **v0.0.1-beta.2 tagged**: SLSA Build Level 2 achieved and formalized.
- **Bot productivity high**: Doom loop broken; backlog populated with complex tasks.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Android test count investigation**: `PocketIdAuthTest` pre-existing failure (`ExceptionInInitializerError` at line 35) — out of bot scope.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Postponed. Prioritizing feature work.
- [ ] **Apply migrate_v6 to production Neon**: `phone_verified`, `phone_verifications`, `scheduler_election` multi-user, `vacation_mode_until` changes.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Open next feature work**: Pick from the high-depth backlog below.
- [ ] **Implement Renovate Configuration (Issue #199)**: Create a centralized `renovate.json` to manage dependencies across all modules (Python, Rust, Android, Web).
- [ ] **Smart Nagging: Success Patterns (Issue #200)**: Implement probability-based nag suppression in `services/smart_nag.py` using historical walk data.
- [ ] **Contextual Awareness: Chrome Bookmarks (Issue #201)**: Build a local Chrome bookmarks parser and MCP endpoint to surface relevant research in the Narrator context.
- [ ] **RAG Foundation: Documentation Graph (Issue #202)**: Standardize doc front-matter and implement automated link/graph verification to prepare for vector indexing.

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

## Infrastructure Notes (carried forward)
- **phone_verified column**: `ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE` — Apply migrate_v6 to production Neon.
- **aggregate_step_count ordering contract**: SQL at `lib.rs:1309` uses `ORDER BY start_time ASC`; `.last()` relies on this.
- **DelayedNagWorker time guards**: Arabic 08:00–20:00; Walk 08:00+; GREEK 17:00–22:30.
- **Moussaka Exception**: `last_greek_nag_timestamp` → 1.5h cooldown. All others: 4h.
- **MECRIS_MODE=standalone** bypasses JWKS; `MECRIS_MODE=cloud` enforces RSA verification.
