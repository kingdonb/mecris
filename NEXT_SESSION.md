# Next Session: Dispatch pr-test for SovereignBrain fallback fix (yebyen/mecris#205)

## Current Status (2026-04-17)
- **SovereignBrain fallback fix committed**: `SovereignBrain.goalSpecificFallback()` companion object added (commit `59c1bc5`). Arabic/Walk nags now get goal-appropriate fallback text when Gemini Nano inference fails. Moussaka fallback preserved for GREEK only.
- **4 unit tests added**: `SovereignBrainFallbackTest` (commit `ee2126e`) — Arabic, Walk, GREEK, and unknown goal cases all covered. Tests will be validated via pr-test CI.
- **Repos**: yebyen/mecris is 2 commits ahead of kingdonb/mecris main (workflow will push at session end).
- **kingdonb/mecris#168 closed**: Phase 4 (Profile Page & Heartbeat) fully complete as of 2026-04-17.

## Verified This Session
- [x] **Root cause identified**: `SovereignBrain.kt:72` used hard-coded Greek moussaka fallback for ALL goals — caused Arabic nags at 8am to show "The moussaka is waiting" when on-device LLM inference failed.
- [x] **TDG complete**: Red (`ee2126e`) + Green (`59c1bc5`) committed.
- [x] **Plan issue yebyen/mecris#205**: Commented with work summary; closed by archive.
- [x] **yebyen/mecris#204 (log out) and kingdonb/mecris#168 (Phase 4)**: Both closed this session cycle.

## Pending Verification (Next Session)
- [ ] **Open PR to kingdonb/mecris**: After workflow pushes yebyen:main (2 commits ahead), open PR for SovereignBrain fallback fix + log out button. Command: `GH_TOKEN="$GITHUB_CLASSIC_PAT" gh pr create --repo kingdonb/mecris --head yebyen:main --base main --title "fix(android): goal-specific LLM fallback text in SovereignBrain + log out button"`.
- [ ] **Dispatch pr-test**: After PR is opened, dispatch pr-test to validate `SovereignBrainFallbackTest` (4 cases) alongside existing Android suite. Expected: Python 461 passed (5 skipped), Rust 99 passed, Android BUILD SUCCESSFUL including `SovereignBrainFallbackTest`.
- [ ] **Secondary DelayedNagWorker message bug**: `DelayedNagWorker.kt:135` message "The moussaka is waiting, but the cards come first" always implies Arabic is undone, even when `arabicCleared = true` fires it. Harmless but misleading. Consider fixing in a future session.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. (Needs human with Fermyon access.)
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.

## Infrastructure Notes
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (GET/POST): Per-user consent flag + `last_autonomous_sync` tracking. Guarded by `internal_api_key` Spin variable (backwards compat: no key = allow all).
  - `/internal/trigger-reminders` (GET/POST): Sends reminders only to users with `autonomous_sync_enabled = true`. Guarded by same key.
- **ProfilePreferencesManager**: Reads/writes `mecris_app_prefs` SharedPreferences. Keys: `preferred_health_source`, `phone_number`, `beeminder_user`.
- **PocketIdAuth.signOut()**: Clears `auth_prefs`/`auth_state_json` key. Does NOT clear profile prefs (persist across re-login — by design).
- **SovereignBrain**: Local LLM via Google AI Edge SDK (Gemini Nano/AICore). `generateNarrativeDirective()` now uses `goalSpecificFallback(targetGoal)` when model returns null.
- **DelayedNagWorker time guards**: Arabic fires 08:00–20:00; Walk fires 08:00+ (with weather/dark checks); GREEK fires 17:00–22:30 (isMoussakaHour), with Arabic-cleared override after 20:00.
- **Spin Cron trigger**: DISABLED in `spin.toml` — do not re-enable.
- **MECRIS_MODE=standalone** bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- **MASTER_ENCRYPTION_KEY**: Must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope, no `read:org`.
- **Fine-grained PAT**: `GITHUB_TOKEN` scoped to yebyen/mecris only. Cannot create PRs on kingdonb/mecris — use `GITHUB_CLASSIC_PAT`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **Python venv not present in bot runner**: Validate Python tests via pr-test workflow only.
- **Python test count baseline**: 461 passed (5 skipped). Rust: 99 passed. Android: BUILD SUCCESSFUL.
- **Rust satellite crates**: 99 tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false` — user must opt in.
