# Next Session: No immediate Android work — kingdonb/mecris#190 awaits review/merge

## Current Status (2026-04-17)
- **PR #190 open**: kingdonb/mecris#190 — `fix(android): DelayedNagWorker Greek nag message when Arabic already cleared` — pr-test ✅ passed (run 24575109106)
- **yebyen/mecris#207 closed**: All validation criteria confirmed — Python 461 passed, Rust 102 passed, Android 26 tests (including 2 new `DelayedNagWorkerMessageTest` cases)
- **yebyen/mecris is 3 commits ahead of kingdonb/mecris**: `14ab3ae` (red), `eccb8ed` (green), `ed6c1f2` (archive) — not yet merged upstream
- **yebyen/mecris#142 open**: CI Rust `working-directory` fix — still blocked (needs `workflow` PAT scope from kingdonb)

## Verified This Session
- [x] **PR #190 opened**: kingdonb/mecris#190 created via GITHUB_CLASSIC_PAT curl ✅
- [x] **pr-test passed**: run 24575109106 — conclusion: success ✅
- [x] **yebyen/mecris#207 closed**: commented + closed with evidence ✅
- [x] **Session archived**: NEXT_SESSION.md + session_log.md committed

## Pending Verification (Next Session)
- [ ] **PR #190 review/merge**: kingdonb needs to review and merge kingdonb/mecris#190. No bot action needed unless requested.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. (Needs human with Fermyon access.)
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.
- [ ] **Secondary DelayedNagWorker message bug (low priority)**: After 20:00 with `arabicCleared = false`, message still says "cards come first" even though we're past the Arabic priority window. Harmless (Arabic IS still pending), but a softer message could be considered. Not urgent.

## Infrastructure Notes
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (GET/POST): Per-user consent flag + `last_autonomous_sync` tracking. Guarded by `internal_api_key` Spin variable (backwards compat: no key = allow all).
  - `/internal/trigger-reminders` (GET/POST): Sends reminders only to users with `autonomous_sync_enabled = true`. Guarded by same key.
- **ProfilePreferencesManager**: Reads/writes `mecris_app_prefs` SharedPreferences. Keys: `preferred_health_source`, `phone_number`, `beeminder_user`. Setters use `editor.apply()` (async, non-blocking).
- **PocketIdAuth.signOut()**: Clears `auth_prefs`/`auth_state_json` key. Does NOT clear profile prefs (persist across re-login — by design).
- **SovereignBrain**: Local LLM via Google AI Edge SDK (Gemini Nano/AICore). `generateNarrativeDirective()` uses `goalSpecificFallback(targetGoal)` when model returns null.
- **DelayedNagWorker time guards**: Arabic fires 08:00–20:00; Walk fires 08:00+ (with weather/dark checks); GREEK fires 17:00–22:30 (isMoussakaHour), with Arabic-cleared override after 20:00.
- **greekNagMessage**: Companion object method in `DelayedNagWorker`. Returns "The moussaka is waiting!" when `arabicCleared=true`, "...but the cards come first" when `arabicCleared=false`.
- **Spin Cron trigger**: DISABLED in `spin.toml` — do not re-enable.
- **MECRIS_MODE=standalone** bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- **MASTER_ENCRYPTION_KEY**: Must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope, no `read:org`.
- **Fine-grained PAT**: `GITHUB_TOKEN` scoped to yebyen/mecris only. Cannot create PRs on kingdonb/mecris — use `GITHUB_CLASSIC_PAT`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **Python venv not present in bot runner**: Validate Python tests via pr-test workflow only.
- **Python test count baseline**: 461 passed (5 skipped). Rust: 102 passed. Android: 26 tests (24 + 2 DelayedNagWorkerMessageTest).
- **Rust satellite crates**: 99+ tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false` — user must opt in.
- **Phone verification**: E2E test added in `bbfcd23`; Rust crash fixed in `db0aef7` (epoch-based expiry). Twilio Phase 2 live test still blocked (needs Fermyon vars).
