# Next Session: Inspect scraper DEBUG logs for numReviewsToday field, then implement if found

## Current Status (2026-03-27)
- **Repos in sync**: kingdonb/mecris#149 was merged (2026-03-27T17:58:47Z). Both repos share HEAD `9abbfd2`.
- **Field discovery logging added**: `scripts/clozemaster_scraper.py` now logs `sorted(pair.keys())` and `sorted(data.keys())` at DEBUG level on each scraper run. Next live run with `logging.DEBUG` enabled will reveal available Clozemaster API fields.
- **Arabic heuristic still in place**: `mcp_server.py:568` applies `daily_done = int(daily_done / 12)` to convert Arabic points to cards. This stays until `numReviewsToday` (or equivalent) is confirmed in the API.
- **No open bot issues**: yebyen/mecris#12 closed with completion evidence.

## Verified This Session
- [x] kingdonb/mecris#149 merged — repos now in sync (verified via GitHub API).
- [x] `logger.debug` added in `get_review_forecast` and `_enrich_with_api_forecast` in `scripts/clozemaster_scraper.py` (commit `6135f95`).
- [x] `tests/test_clozemaster_idempotency.py` passes (2/2) after the change.

## Pending Verification (Next Session)
- **Field discovery**: Run the Clozemaster scraper with `logging.DEBUG` enabled (set `logging.basicConfig(level=logging.DEBUG)` or `LOG_LEVEL=DEBUG`). Check the output for `"All available pairing keys for ara-eng: [...]"` — note whether `numReviewsToday`, `numSentencesDoneToday`, or similar card-count field appears.
- **If field found**: Add `daily_cards` column to `language_stats` table (see `attic/scripts/update_schema.py` for migration pattern), update `LanguageSyncService._update_neon_db` to store it, update `NeonSyncChecker.get_language_stats` to return it, remove the `/12` heuristic from `mcp_server.py:568`.
- **Skills Discoverability**: Still unverified — confirm if mecris-orient/plan/archive skills are discoverable in a standard Claude Code install (no action path identified yet).

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is the upstream. Sync via PR.
- Bot governor: 80 turns documented limit, 200 turns actual. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log updated at `session_log.md`.
