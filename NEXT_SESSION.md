# Next Session: Field discovery or open next improvement issue from kingdonb/mecris backlog

## Current Status (2026-03-28)
- **kingdonb/mecris#150 merged**: PR was merged on 2026-03-28T12:01:47Z. yebyen/mecris and kingdonb/mecris are in sync at `257df08`.
- **Early-switch bug fixed**: `ARABIC_POINTS_PER_CARD = 16` constant added to `services/review_pump.py`; `mcp_server.py` now uses it instead of magic number `12`. Addresses kingdonb/mecris#151.
- **82/82 tests pass**: Full suite including 5 review pump unit tests (3 new regression guards).
- **Field discovery still blocked**: `scripts/clozemaster_scraper.py` requires live Clozemaster credentials unavailable in the bot environment.

## Verified This Session
- [x] kingdonb/mecris#150 merged (2026-03-28T12:01:47Z) — confirmed via API.
- [x] `/12` → `/16` heuristic fix committed as `38dcd9d`. All 82 tests pass.
- [x] New tests `test_arabic_points_per_card_is_conservative` and `test_arabic_early_switch_prevented` added as regression guards against reverting to /12.
- [x] yebyen/mecris is in sync with kingdonb/mecris (no sync PR needed).

## Pending Verification (Next Session)
- **Open sync PR**: The fix commit (`38dcd9d`) is on yebyen/mecris main but not yet in kingdonb/mecris. Open a PR from yebyen/mecris → kingdonb/mecris carrying `38dcd9d`.
- **kingdonb/mecris#151**: Check if the PR addressing the early-switch bug satisfies the issue owner. Comment on #151 with the fix details.
- **Field discovery**: Run `scripts/clozemaster_scraper.py` with live Clozemaster credentials. Look for `numReviewsToday`, `numSentencesDoneToday`, or direct card-count fields in the DEBUG output. If found, replace the `/16` heuristic with exact card data.
- **If field found**: Add `daily_cards` column to `language_stats` table (see `attic/scripts/update_schema.py` for migration pattern), update `LanguageSyncService._update_neon_db` to store it, update `NeonSyncChecker.get_language_stats` to return it, remove `ARABIC_POINTS_PER_CARD` heuristic from `mcp_server.py`.
- **Other backlog**: kingdonb/mecris has 20 open issues. Consider picking up kingdonb/mecris#128 (Greek Beeminder slug correction) or #122 (Android multiplier persistence race).

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is the upstream. Sync via PR.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- Field discovery CANNOT be done by mecris-bot — requires live credentials. Consider running manually or building a fixture.
- Full test suite requires pyproject.toml deps (including `mcp[cli]`, `apscheduler`, `sqlalchemy`, `beautifulsoup4`, `playwright`). TDG.md build command updated accordingly in `7305a45`.
- `ARABIC_POINTS_PER_CARD = 16` is now the single source of truth for the Arabic points-per-card constant (in `services/review_pump.py`). Do not change without also checking `test_arabic_points_per_card_is_conservative`.
