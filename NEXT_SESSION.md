# Next Session: Check if kingdonb/mecris#150 was merged; field discovery still requires human credentials

## Current Status (2026-03-28)
- **Sync PR still open**: kingdonb/mecris#150 carries 7 commits (through `7305a45`). A status comment was posted 2026-03-28. Awaiting merge by kingdonb.
- **Full test suite verified**: 82/82 tests pass including all 4 `test_coaching.py` tests. Confirmed with full `.venv` install from pyproject.toml deps.
- **TDG.md build command fixed**: Old command (`uv pip install -r requirements.txt ...`) omitted `mcp[cli]`, `apscheduler`, `sqlalchemy`. Updated to include these (`7305a45`).
- **Field discovery still blocked**: `scripts/clozemaster_scraper.py` requires live Clozemaster credentials unavailable in the bot environment.

## Verified This Session
- [x] kingdonb/mecris#150 is still open (2026-03-28) — kingdonb has not yet merged it.
- [x] `test_coaching.py` 4 tests execute and pass (not just collect). Full suite: 82/82 passed.
- [x] Missing deps (`mcp[cli]`, `apscheduler`, `sqlalchemy`) identified and TDG.md fixed (`7305a45`).
- [x] Status comment posted on kingdonb/mecris#150 with test results.

## Pending Verification (Next Session)
- **Check PR merge status**: Confirm kingdonb/mecris#150 was merged. If not, follow up again.
- **Field discovery**: Run `scripts/clozemaster_scraper.py` with live Clozemaster credentials. Look for `"All available pairing keys for ara-eng: [...]"` in DEBUG output. Note whether `numReviewsToday`, `numSentencesDoneToday`, or similar direct card-count field appears.
- **If field found**: Add `daily_cards` column to `language_stats` table (see `attic/scripts/update_schema.py` for migration pattern), update `LanguageSyncService._update_neon_db` to store it, update `NeonSyncChecker.get_language_stats` to return it, remove the `/12` heuristic from `mcp_server.py:568`.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is the upstream. Sync via PR.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- Field discovery CANNOT be done by mecris-bot — requires live credentials. Consider running manually or building a fixture.
- Full test suite now requires pyproject.toml deps, not just requirements.txt. TDG.md build command updated accordingly.
