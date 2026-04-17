# Next Session: kingdonb/mecris#192 awaits review/merge (Ghost Nag fix — PR open, pr-test ✅)

## Current Status (2026-04-17)
- **PR #192 open**: kingdonb/mecris#192 — Ghost Nag prevention: Cloud cron checks `scheduler_election` for fresh `android_client` heartbeat (within 4h) and stands down if found. Addresses kingdonb/mecris#191.
- **yebyen/mecris is 2 commits ahead of kingdonb/mecris**: `0f335e3` (red) + `7a26619` (green)
- **pr-test ✅ passed**: run 24584600085 — conclusion: success
- **yebyen/mecris#209 closed**: Plan issue for Ghost Nag fix — TDG complete, pr-test passed
- **yebyen/mecris#142 open**: CI Rust `working-directory` fix — still blocked (needs `workflow` PAT scope from kingdonb)
- **Pre-existing test failures**: Python (`phone_verified` column missing in test DB) and Android (`PocketIdAuthTest` ExceptionInInitializerError) — both pre-existing, not caused by this work

## Verified This Session
- [x] **PR #190 merged**: `da6aaba Merge bot changes` — greekNagMessage fixes landed on kingdonb/mecris main
- [x] **TDG red+green**: `0f335e3` (failing test for `android_client_is_active`) + `7a26619` (implementation + DB integration) — committed to yebyen:main
- [x] **pr-test ✅ passed**: run 24584600085 — conclusion: success, 107 Rust tests passed
- [x] **PR #192 opened**: kingdonb/mecris#192 — Ghost Nag fix, ready for review
- [x] **yebyen/mecris#209 closed**: Plan issue closed with evidence

## Pending Verification (Next Session)
- [ ] **PR #192 review/merge**: kingdonb needs to review and merge kingdonb/mecris#192 (Ghost Nag fix). No bot action needed unless requested.
- [ ] **Rust test count increased**: pr-test now shows 107 Rust tests (was 102). Baseline updated.
- [ ] **Android test count investigation**: pr-test shows "26 tests completed, 1 failed" — expected 27 after greekNagMessage tests. May be Gradle counting artifact. Worth checking after PR #192 merges.
- [ ] **kingdonb/mecris#191 full resolution**: Issue tracks two options (A: leader election, B: Android logs to message_log). PR #192 implements Option A. Option B (Android-side logging) could complement but is not required for the first fix.
- [ ] **Configure internal_api_key in Fermyon Cloud**: Set `internal_api_key = "<secret>"` in runtime-config; update Akamai cron `curl` calls with `X-Internal-Api-Key: <secret>`. (Needs human with Fermyon access.)
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT scope — must be applied by kingdonb.

## Infrastructure Notes
- **android_client_is_active**: `android_client_is_active(heartbeat_age_minutes: Option<u64>) -> bool` — returns `true` if Android heartbeated within 240 minutes (4 hours). Integrated into `handle_trigger_reminders_post` in `sync-service/src/lib.rs`.
- **Ghost Nag guard query**: `SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60 AS minutes_since FROM scheduler_election WHERE user_id = $1 AND role = 'android_client' ORDER BY heartbeat DESC LIMIT 1`
- **greekNagMessage signature**: `greekNagMessage(arabicCleared: Boolean, isArabicHour: Boolean = true)` — default `true` preserves backwards compat.
- **DelayedNagWorker time guards**: Arabic fires 08:00–20:00; Walk fires 08:00+ (with weather/dark checks); GREEK fires 17:00–22:30 (isMoussakaHour), with Arabic-cleared override after 20:00.
- **Majesty Cake**: When `walkingSessionsCount > 0` or `totalDistanceMeters > 0.0` but `totalSteps < 2000`, Android nags use "MAJESTY CAKE 🍰" framing instead of standard Boris & Fiona walk nag.
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (GET/POST): Per-user consent flag + `last_autonomous_sync` tracking. Guarded by `internal_api_key` Spin variable (backwards compat: no key = allow all).
  - `/internal/trigger-reminders` (GET/POST): Sends reminders only to users with `autonomous_sync_enabled = true`. Guarded by same key.
- **ProfilePreferencesManager**: Reads/writes `mecris_app_prefs` SharedPreferences. Keys: `preferred_health_source`, `phone_number`, `beeminder_user`. Setters use `editor.apply()` (async, non-blocking).
- **SovereignBrain**: Local LLM via Google AI Edge SDK (Gemini Nano/AICore). `generateNarrativeDirective()` uses `goalSpecificFallback(targetGoal)` when model returns null.
- **Spin Cron trigger**: DISABLED in `spin.toml` — do not re-enable.
- **MECRIS_MODE=standalone** bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- **MASTER_ENCRYPTION_KEY**: Must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope, no `read:org`.
- **Fine-grained PAT**: `GITHUB_TOKEN` scoped to yebyen/mecris only. Cannot create PRs on kingdonb/mecris — use `GITHUB_CLASSIC_PAT`.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **Python venv not present in bot runner**: Validate Python tests via pr-test workflow only.
- **Python test count baseline**: 461 passed (5 skipped) — 1 failing (`test_phone_verification_lifecycle`, pre-existing schema issue). Rust: 107 passed (was 102, +5 new ghost nag tests). Android: 26 tests (25 pass + 1 PocketIdAuthTest failure, pre-existing).
- **Rust satellite crates**: 99+ tests in sync-service, 28 in boris-fiona-walker, others not in CI yet.
- **autonomous_sync_enabled**: DB flag per user (`users` table). Controls which users get processed by `/internal/trigger-reminders`. Default `false` — user must opt in.
- **Phone verification**: E2E test added in `bbfcd23`; Rust crash fixed in `db0aef7` (epoch-based expiry). Twilio Phase 2 live test still blocked (needs Fermyon vars).
