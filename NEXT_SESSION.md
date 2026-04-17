# Next Session: Open PR for DelayedNagWorker fix (commits pushed, awaiting pr-test)

## Current Status (2026-04-17)
- **TDG cycle complete**: `14ab3ae` (red: DelayedNagWorkerMessageTest) + `eccb8ed` (green: greekNagMessage companion object) committed locally
- **PR not yet open**: GitHub reports "No commits between kingdonb:main and yebyen:main" — push happens via workflow at session end; PR must be opened NEXT session
- **Both repos were in sync** at `bbfcd23` when this session started; yebyen is now 2 commits ahead after the fix
- **PR #189 merged**: kingdonb/mecris#189 was merged before this session began (2026-04-17T12:25:26Z) — that task is fully complete
- **Plan issue yebyen/mecris#207** open — to be closed after pr-test confirms green

## Verified This Session
- [x] **PR #189 merged**: kingdonb/mecris#189 closed 2026-04-17T12:25:26Z ✅
- [x] **Both repos synced**: yebyen and kingdonb both at `bbfcd23` at session start ✅
- [x] **Bug identified**: `DelayedNagWorker.kt:135` hardcoded "cards come first" message regardless of `arabicCleared` state
- [x] **Red test committed**: `14ab3ae` — `DelayedNagWorkerMessageTest` with 2 cases (arabic-cleared, arabic-pending)
- [x] **Green fix committed**: `eccb8ed` — `greekNagMessage(arabicCleared: Boolean)` companion object; line 135 replaced with call to it

## Pending Verification (Next Session)
- [ ] **Open PR yebyen:main → kingdonb:main**: After workflow pushes commits, create PR. Command: `curl -X POST -H "Authorization: Bearer $GITHUB_CLASSIC_PAT" -H "Accept: application/vnd.github+json" -H "Content-Type: application/json" -d '{"title":"fix(android): DelayedNagWorker Greek nag message when Arabic already cleared","head":"yebyen:main","base":"main","body":"Tracked in yebyen/mecris#207"}' https://api.github.com/repos/kingdonb/mecris/pulls`
- [ ] **Run pr-test**: Dispatch pr-test workflow for the new PR. Expected: Python 461 passed, Rust 102 passed, Android BUILD SUCCESSFUL with `DelayedNagWorkerMessageTest` 2 cases passing
- [ ] **Close yebyen/mecris#207**: After pr-test passes, close plan issue with ✅ Complete comment
- [ ] **Secondary DelayedNagWorker message bug (partial)**: After 20:00 with `arabicCleared = false`, the message still says "cards come first" even though we're past the Arabic priority window. Harmless (it IS still true you haven't done Arabic), but consider a softer message. Not urgent.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. (Needs human with Fermyon access.)
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.

## Infrastructure Notes
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (GET/POST): Per-user consent flag + `last_autonomous_sync` tracking. Guarded by `internal_api_key` Spin variable (backwards compat: no key = allow all).
  - `/internal/trigger-reminders` (GET/POST): Sends reminders only to users with `autonomous_sync_enabled = true`. Guarded by same key.
- **ProfilePreferencesManager**: Reads/writes `mecris_app_prefs` SharedPreferences. Keys: `preferred_health_source`, `phone_number`, `beeminder_user`. Setters use `editor.apply()` (async, non-blocking) — fixed in PR#189.
- **PocketIdAuth.signOut()**: Clears `auth_prefs`/`auth_state_json` key. Does NOT clear profile prefs (persist across re-login — by design).
- **SovereignBrain**: Local LLM via Google AI Edge SDK (Gemini Nano/AICore). `generateNarrativeDirective()` uses `goalSpecificFallback(targetGoal)` when model returns null.
- **DelayedNagWorker time guards**: Arabic fires 08:00–20:00; Walk fires 08:00+ (with weather/dark checks); GREEK fires 17:00–22:30 (isMoussakaHour), with Arabic-cleared override after 20:00.
- **greekNagMessage**: New companion object method in `DelayedNagWorker`. Returns "The moussaka is waiting!" when `arabicCleared=true`, "...but the cards come first" when `arabicCleared=false`.
- **Spin Cron trigger**: DISABLED in `spin.toml` — do not re-enable.
- **MECRIS_MODE=standalone** bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- **MASTER_ENCRYPTION_KEY**: Must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope, no `read:org`.
- **Fine-grained PAT**: `GITHUB_TOKEN` scoped to yebyen/mecris only. Cannot create PRs on kingdonb/mecris — use `GITHUB_CLASSIC_PAT`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **Python venv not present in bot runner**: Validate Python tests via pr-test workflow only.
- **Python test count baseline**: 461 passed (5 skipped). Rust: 102 passed. Android: 24 tests (+ 2 new DelayedNagWorkerMessageTest cases = 26 total expected).
- **Rust satellite crates**: 99+ tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false` — user must opt in.
- **Phone verification**: E2E test added in `bbfcd23`; Rust crash fixed in `db0aef7` (epoch-based expiry). Twilio Phase 2 live test still blocked (needs Fermyon vars).
