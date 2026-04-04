# Next Session: Start Greek Backlog Booster design (kingdonb/mecris#129)

## Current Status (Saturday, April 4, 2026 — session 30)
- **Repos in sync**: Reconciled with `yebyen/mecris-bot` and integrated "Actual Card Count" logic from stash.
- **Walk Logic Objective**: Python `has_walk_today` now recognizes logged Workouts and distance (1.0 mi) as qualification, and step threshold is synchronized at **2,000 steps** across Python and Android.
- **Android Auth Resilience**: `PocketIdAuth.kt` updated to update `_authState` on successful refresh and trigger silent refresh during state load if a refresh token is present.
- **WASM-Brain Plan**: Created `docs/WASM_BRAIN_PLAN.md` to track migration candidates for local-first execution.
- **Spin Deployed**: `mecris-sync-v2` redeployed with latest Majesty Cake and Cloud Sync logic.
- **Audit session verified**: kingdonb/mecris#121 and #122 confirmed complete.
- **249 passed** in full test suite.

## Verified This Session
- [x] Walk threshold synchronized at 2,000 steps. ✅
- [x] Python recognizes logged activity/workouts for walk qualification. ✅
- [x] Android auth state restores correctly after refresh. ✅
- [x] Spin backend redeployed with Majesty Cake components. ✅
- [x] "Actual Card Count" extraction from Clozemaster integrated. ✅

## Pending Verification (Next Session)

### Issues to Close (Requires kingdonb)
- **kingdonb/mecris#162** — OIDC fixes implemented + merged.
- **kingdonb/mecris#130** — Score-delta tracking implemented + merged.
- **kingdonb/mecris#132** — "FIXED: Failover sync" — comment posted session 29.
- **kingdonb/mecris#121** — Language dashboard sorting.
- **kingdonb/mecris#122** — Multiplier race condition.

### Next Feature Work
- **kingdonb/mecris#129 — Greek Backlog Booster**: Design a "Stack Vitality" incentive to encourage playing new Greek cards when the review well runs dry, eventually leading to a dedicated backlog goal.

### Live Validation (carry-forward, requires live env)
- SQL migration: `psql $NEON_DB_URL -f scripts/migrations/001_presence_table.sql`
- `get_system_health` live validation: should return `scheduler_election` rows, not error
- Ghost Archivist: `logs/ghost_archivist.log` should accumulate PULSE entries
- `get_daily_aggregate_status` live call — verify walk status reflects actual Neon DB state
- `get_narrator_context` live call — verify `daily_aggregate_status` key appears with real data AND recommendation ordering is as expected

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **WASM-brain Plan**: See `docs/WASM_BRAIN_PLAN.md` for candidates.
- **Nag Ladder tier semantics**: Tier 1 (WhatsApp Template), Tier 2 (Freeform), Tier 3 (Urgent, runway < 2h).
- **Android multiplier race guard**: `surgicalUpdateInProgress` flag — 5 layers of protection.
