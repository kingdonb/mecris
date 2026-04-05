# Next Session: Ghost Archivist Phase B or next open epic

## Current Status (Saturday, April 4, 2026 — session 32)
- **Test suite clean**: 252 passed, 0 failed, 4 skipped. Two stale tests repaired (yebyen/mecris#93).
- **Ghost Archivist Phase A**: Already fully implemented. `ghost/archivist.py`, `ghost/presence.py`, `scripts/migrations/001_presence_table.sql`, and 46 unit tests all green. Phase A was more complete than NEXT_SESSION.md suggested.
- **kingdonb/mecris#129**: Greek Backlog Booster — implemented + tested. Issue still open (needs kingdonb to close).
- **Ghost Archivist Phases B + C**: Phase B (`mecris internal presence` CLI handle) and Phase C (`archivists_round_robin()` scheduler) are not yet implemented. Spec at `docs/GHOST_ARCHIVIST_SPEC.md`.

## Verified This Session
- [x] Ghost Archivist Phase A fully implemented: `ghost/presence.py` (236 lines), `ghost/archivist.py` (104 lines), `001_presence_table.sql`, 46 tests green. ✅
- [x] 252 tests passing, 0 failing (was 2 failing before this session). ✅
- [x] `test_neon_sync_checker_initialization`: stale `default_user_id` assertion removed. ✅
- [x] `test_language_sync_service_coordination`: patched `UsageTracker.resolve_user_id` so mock UUID matches, no rogue BeeminderClient spawned in CI. ✅

## Pending Verification (Next Session)

### Issues to Close (Requires kingdonb)
- **kingdonb/mecris#162** — OIDC fixes implemented + merged.
- **kingdonb/mecris#130** — Score-delta tracking implemented + merged.
- **kingdonb/mecris#132** — "FIXED: Failover sync" — comment posted session 29.
- **kingdonb/mecris#121** — Language dashboard sorting (audit confirmed complete session 30).
- **kingdonb/mecris#122** — Multiplier race condition (audit confirmed complete session 30).
- **kingdonb/mecris#129** — Greek Backlog Booster: implemented + tested. Ready for closure.

### Next Feature Work
- **Ghost Archivist Phase B**: Add `mecris internal presence` CLI subcommand (see `docs/GHOST_ARCHIVIST_SPEC.md` §Phase B). Check `cli/main.py` for existing presence hooks.
- **Ghost Archivist Phase C**: Add `archivists_round_robin()` background job to `scheduler.py`. Runs every 4 hours, triggers archival turn when human is silent after 10pm Eastern.
- **kingdonb/mecris#170 — Majesty Cake Epic**: Backend `get_daily_aggregate_status` implemented, Android `MajestyCakeWidget` confirmed present. Epic should be closeable.

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
- **Ghost Archivist schema**: Migration creates `presence` table (NOT `user_presence` as older spec draft stated). Status enum: `pulse`, `active_human`, `needs_attention`, `pound_sand`, `shits_on_fire_yo`.
