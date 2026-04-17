# Next Session: kingdonb/mecris#190 awaits review/merge (now includes two Greek nag fixes)

## Current Status (2026-04-17)
- **PR #190 open**: kingdonb/mecris#190 — now covers TWO fixes: (1) `greekNagMessage` when `arabicCleared=true` (previous session), (2) `greekNagMessage` after Arabic time window closes 20:00+ when `arabicCleared=false` (this session)
- **yebyen/mecris is 5 commits ahead of kingdonb/mecris**: `14ab3ae` (red1), `eccb8ed` (green1), `62edaaa` (red2), `89507b1` (green2) + archive — not yet merged upstream
- **yebyen/mecris#208 closed**: DelayedNagWorker Arabic-window timing fix — TDG complete, pr-test ✅ success (run 24579777635)
- **yebyen/mecris#142 open**: CI Rust `working-directory` fix — still blocked (needs `workflow` PAT scope from kingdonb)
- **Pre-existing test failures**: Python (`phone_verified` column missing in test DB) and Android (`PocketIdAuthTest` ExceptionInInitializerError) — both present before this session, not caused by this work

## Verified This Session
- [x] **TDG red+green**: `62edaaa` (failing test for `isArabicHour=false`) + `89507b1` (fix: `greekNagMessage` accepts `isArabicHour: Boolean = true`) — committed to yebyen:main
- [x] **pr-test ✅ passed**: run 24579777635 — conclusion: success
- [x] **yebyen/mecris#208 closed**: commented + closed with evidence ✅

## Pending Verification (Next Session)
- [ ] **PR #190 review/merge**: kingdonb needs to review and merge kingdonb/mecris#190 (now includes both `greekNagMessage` fixes). No bot action needed unless requested.
- [ ] **Android test count investigation**: pr-test shows "26 tests completed, 1 failed" — same count as before adding the new `isArabicHour` test case. Expected 27. May be Gradle counting artifact or the new test wasn't picked up by this run. Worth verifying in next pr-test run after PR #190 merges.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. (Needs human with Fermyon access.)
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.

## Infrastructure Notes
- **greekNagMessage signature**: `greekNagMessage(arabicCleared: Boolean, isArabicHour: Boolean = true)` — default `true` preserves backwards compat. Callsite passes `localHour < 20`.
- **DelayedNagWorker time guards**: Arabic fires 08:00–20:00; Walk fires 08:00+ (with weather/dark checks); GREEK fires 17:00–22:30 (isMoussakaHour), with Arabic-cleared override after 20:00.
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (GET/POST): Per-user consent flag + `last_autonomous_sync` tracking. Guarded by `internal_api_key` Spin variable (backwards compat: no key = allow all).
  - `/internal/trigger-reminders` (GET/POST): Sends reminders only to users with `autonomous_sync_enabled = true`. Guarded by same key.
- **ProfilePreferencesManager**: Reads/writes `mecris_app_prefs` SharedPreferences. Keys: `preferred_health_source`, `phone_number`, `beeminder_user`. Setters use `editor.apply()` (async, non-blocking).
- **PocketIdAuth.signOut()**: Clears `auth_prefs`/`auth_state_json` key. Does NOT clear profile prefs (persist across re-login — by design).
- **SovereignBrain**: Local LLM via Google AI Edge SDK (Gemini Nano/AICore). `generateNarrativeDirective()` uses `goalSpecificFallback(targetGoal)` when model returns null.
- **Spin Cron trigger**: DISABLED in `spin.toml` — do not re-enable.
- **MECRIS_MODE=standalone** bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- **MASTER_ENCRYPTION_KEY**: Must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope, no `read:org`.
- **Fine-grained PAT**: `GITHUB_TOKEN` scoped to yebyen/mecris only. Cannot create PRs on kingdonb/mecris — use `GITHUB_CLASSIC_PAT`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **Python venv not present in bot runner**: Validate Python tests via pr-test workflow only.
- **Python test count baseline**: 461 passed (5 skipped) — 1 failing (`test_phone_verification_lifecycle`, pre-existing schema issue). Rust: 102 passed. Android: 26 tests (25 pass + 1 PocketIdAuthTest failure, pre-existing).
- **Rust satellite crates**: 99+ tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false` — user must opt in.
- **Phone verification**: E2E test added in `bbfcd23`; Rust crash fixed in `db0aef7` (epoch-based expiry). Twilio Phase 2 live test still blocked (needs Fermyon vars).
