# Next Session: Continue Greek Backlog Booster work and verify kingdonb/mecris#129 closure

## Current Status (Saturday, April 4, 2026 — session 31)
- **Recommendation ordering fixed**: Greek Stack Vitality coaching now follows the Majesty Cake daily aggregate block in `get_narrator_context`, restoring correct priority (urgent → Majesty Cake → Greek coaching → walk).
- **All 21 tests green**: `test_greek_backlog_booster` (8/8) and `test_daily_aggregate_status` + `test_narrator_aggregate_integration` (13/13) all pass.
- **kingdonb/mecris#129**: Greek Backlog Booster is implemented — `_greek_backlog_active()` in `language_sync_service.py`, coaching in `get_narrator_context`, 8 unit tests. Issue still open (needs kingdonb to close).
- **Ghost Archivist spec**: `docs/GHOST_ARCHIVIST_SPEC.md` exists — spec only, not implemented.

## Verified This Session
- [x] Recommendation ordering: Majesty Cake progress precedes Greek coaching. ✅
- [x] 21 tests pass across Greek backlog booster + Majesty Cake test suite. ✅
- [x] `_greek_backlog_active()` static method with GREEK_BACKLOG_THRESHOLD constant. ✅

## Pending Verification (Next Session)

### Issues to Close (Requires kingdonb)
- **kingdonb/mecris#162** — OIDC fixes implemented + merged.
- **kingdonb/mecris#130** — Score-delta tracking implemented + merged.
- **kingdonb/mecris#132** — "FIXED: Failover sync" — comment posted session 29.
- **kingdonb/mecris#121** — Language dashboard sorting (audit confirmed complete session 30).
- **kingdonb/mecris#122** — Multiplier race condition (audit confirmed complete session 30).
- **kingdonb/mecris#129** — Greek Backlog Booster: implemented + tested. Ready for closure.

### Next Feature Work
- **kingdonb/mecris#170 — Majesty Cake Epic**: Backend `get_daily_aggregate_status` implemented. Next: Android UI widget integration (Phase 4 may already be done — verify `MajestyCakeWidget` exists in Android code).
- **Ghost Archivist (docs/GHOST_ARCHIVIST_SPEC.md)**: Spec written, not implemented. Phase A: `user_presence` table schema migration.

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
