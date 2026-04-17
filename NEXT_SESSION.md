# Next Session: Re-run pr-test for kingdonb/mecris#189 (Android fix committed, needs push+validate)

## Current Status (2026-04-17)
- **PR open**: kingdonb/mecris#189 — yebyen:main → kingdonb:main (SovereignBrain fallback fix + log out button). 4 commits ahead of kingdonb:main now (was 3; green fix added this session).
- **Android regression fixed**: `5946d4e` had changed `Editor.apply()` → `Editor.commit()` in `ProfilePreferencesManager.kt`, breaking 4 tests in `ProfilePreferencesManagerTest`. Fixed in commit `57acd70` (green: restore apply()). Fix is local — pushed by workflow at session end.
- **pr-test result (run #24564190870)**: ✅ Python 461 passed (5 skipped) | ✅ Rust 102 passed | ❌ Android 5 failed (all in ProfilePreferencesManagerTest, pre-existing regression from 5946d4e).
- **SovereignBrainFallbackTest**: Likely passed (4 tests), confirmed indirectly — the Android failure report only named ProfilePreferencesManagerTest failures.

## Verified This Session
- [x] **PR opened**: kingdonb/mecris#189 created from yebyen:main → kingdonb:main
- [x] **pr-test dispatched and completed**: run #24564190870, Python/Rust clean
- [x] **Android root cause identified**: `commit()` vs `apply()` mismatch in ProfilePreferencesManager.kt (5946d4e regression)
- [x] **Green fix committed**: `57acd70` — ProfilePreferencesManager setters now use `editor.apply()`
- [x] **Plan issue yebyen/mecris#206**: commented with root cause + fix details; closed by archive

## Pending Verification (Next Session)
- [ ] **Re-run pr-test for kingdonb/mecris#189**: After workflow pushes the green fix (57acd70), dispatch pr-test. Command: `curl -X POST -H "Authorization: Bearer $GITHUB_CLASSIC_PAT" -H "Accept: application/vnd.github+json" -H "Content-Type: application/json" -d '{"ref":"main","inputs":{"pr_number":"189","upstream_repo":"kingdonb/mecris"}}' https://api.github.com/repos/yebyen/mecris/actions/workflows/pr-test.yml/dispatches`. Expected: Python 461 passed, Rust 102 passed, Android BUILD SUCCESSFUL (24 tests, 0 failed including SovereignBrainFallbackTest 4 cases and ProfilePreferencesManagerTest 8 cases).
- [ ] **Identify 5th failing Android test**: pr-test showed 5 failed but ProfilePreferencesManagerTest only has 4 `apply()` verify checks. If re-run still shows a 5th failure, investigate which test class.
- [ ] **Merge kingdonb/mecris#189**: After pr-test passes, request merge.
- [ ] **Secondary DelayedNagWorker message bug**: `DelayedNagWorker.kt:135` message "The moussaka is waiting, but the cards come first" always implies Arabic is undone, even when `arabicCleared = true` fires it. Harmless but misleading. Consider fixing in a future session.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. (Needs human with Fermyon access.)
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.

## Infrastructure Notes
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (GET/POST): Per-user consent flag + `last_autonomous_sync` tracking. Guarded by `internal_api_key` Spin variable (backwards compat: no key = allow all).
  - `/internal/trigger-reminders` (GET/POST): Sends reminders only to users with `autonomous_sync_enabled = true`. Guarded by same key.
- **ProfilePreferencesManager**: Reads/writes `mecris_app_prefs` SharedPreferences. Keys: `preferred_health_source`, `phone_number`, `beeminder_user`. Setters now use `editor.apply()` (async, non-blocking) — restored from regression.
- **PocketIdAuth.signOut()**: Clears `auth_prefs`/`auth_state_json` key. Does NOT clear profile prefs (persist across re-login — by design).
- **SovereignBrain**: Local LLM via Google AI Edge SDK (Gemini Nano/AICore). `generateNarrativeDirective()` uses `goalSpecificFallback(targetGoal)` when model returns null.
- **DelayedNagWorker time guards**: Arabic fires 08:00–20:00; Walk fires 08:00+ (with weather/dark checks); GREEK fires 17:00–22:30 (isMoussakaHour), with Arabic-cleared override after 20:00.
- **Spin Cron trigger**: DISABLED in `spin.toml` — do not re-enable.
- **MECRIS_MODE=standalone** bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- **MASTER_ENCRYPTION_KEY**: Must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope, no `read:org`.
- **Fine-grained PAT**: `GITHUB_TOKEN` scoped to yebyen/mecris only. Cannot create PRs on kingdonb/mecris — use `GITHUB_CLASSIC_PAT`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **Python venv not present in bot runner**: Validate Python tests via pr-test workflow only.
- **Python test count baseline**: 461 passed (5 skipped). Rust: 102 passed (was 99, grew this cycle). Android: 24 tests, 5 failed (will be 0 failed after 57acd70 is included).
- **Rust satellite crates**: 99+ tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false` — user must opt in.
