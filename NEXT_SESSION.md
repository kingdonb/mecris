# Next Session: Check if kingdonb/mecris#150 was merged; field discovery still requires human credentials

## Current Status (2026-03-27)
- **Sync PR still open**: kingdonb/mecris#150 carries commits `9c9e8fc` (docs: Arabic unit duality) and `3f150a4` (archive). Awaiting merge by kingdonb.
- **Field discovery still blocked**: `scripts/clozemaster_scraper.py` has DEBUG logging (`6135f95`), but running it requires live Clozemaster credentials unavailable in the bot environment.
- **Test suite health improved**: 11 pre-existing test failures fixed (commit `ccc472b`). 78/78 non-integration tests pass. `tests/test_coaching.py` still cannot be collected — it imports `mcp_server` which instantiates `UsageTracker()` at module level, requiring NEON_DB_URL.
- **Arabic heuristic clarified**: `mcp_server.py:568` divides `daily_completions` by 12. Comment updated (`9c9e8fc`) to document the dual-path reality.

## Verified This Session
- [x] kingdonb/mecris#150 is still open (2026-03-27) — kingdonb has not yet merged it.
- [x] 11 pre-existing test failures repaired across 5 test files (commit `ccc472b`).
  - `test_budget_hard_stop.py`: added NEON_DB_URL to fixture env
  - `test_multi_tenancy.py`: patched `resolve_user_id`, added 6th tuple element for `daily_completions`
  - `test_scheduler_election.py`: added `DEFAULT_USER_ID` to fixture env
  - `test_language_sync_service.py`: moved service creation inside `patch.dict(NEON_DB_URL)` context
  - `test_reminder_integration.py`: evict `sys.modules["mcp_server"]` + patch `psycopg2.connect` before import
- [x] All 78 non-integration tests pass cleanly.

## Pending Verification (Next Session)
- **Check PR merge status**: Confirm kingdonb/mecris#150 was merged. If not, follow up.
- **Field discovery**: Run `scripts/clozemaster_scraper.py` with live Clozemaster credentials. Look for `"All available pairing keys for ara-eng: [...]"` in DEBUG output. Note whether `numReviewsToday`, `numSentencesDoneToday`, or similar direct card-count field appears.
- **If field found**: Add `daily_cards` column to `language_stats` table (see `attic/scripts/update_schema.py` for migration pattern), update `LanguageSyncService._update_neon_db` to store it, update `NeonSyncChecker.get_language_stats` to return it, remove the `/12` heuristic from `mcp_server.py:568`.
- **test_coaching.py**: Still fails at collection because `mcp_server` instantiates `UsageTracker()` at module level. Needs same treatment as `test_reminder_integration.py` — evict `sys.modules["mcp_server"]` + patch psycopg2 before import.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is the upstream. Sync via PR.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- Field discovery CANNOT be done by mecris-bot — requires live credentials. Consider running manually or building a fixture.
- `test_coaching.py` excluded from bot test runs until module-level UsageTracker init is fixed.
