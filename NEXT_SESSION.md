# Next Session: Check if kingdonb/mecris#150 was merged; field discovery still requires human credentials

## Current Status (2026-03-28)
- **Sync PR still open**: kingdonb/mecris#150 now carries 5 commits (through `6c6e1df`). Awaiting merge by kingdonb.
- **Field discovery still blocked**: `scripts/clozemaster_scraper.py` has DEBUG logging, but running it requires live Clozemaster credentials unavailable in the bot environment.
- **Test suite health**: `test_coaching.py` collection failure fixed (`6c6e1df`). 78/78 non-integration tests pass. `test_coaching.py` now collects 4 additional tests — full pass count pending CI run with `.venv`.
- **Arabic heuristic clarified**: `mcp_server.py:568` divides `daily_completions` by 12. Comment updated (`9c9e8fc`) to document the dual-path reality.

## Verified This Session
- [x] kingdonb/mecris#150 is still open (2026-03-28) — kingdonb has not yet merged it.
- [x] `test_coaching.py` collection failure fixed: module-level import removed, `_make_mcp_importable()` helper added, `sys.modules.pop("mcp_server", None)` + deferred import applied in each test. `pytest --collect-only tests/test_coaching.py` now reports 4 tests, 0 errors (was: 1 import error, 0 tests). Commit `6c6e1df`.

## Pending Verification (Next Session)
- **Check PR merge status**: Confirm kingdonb/mecris#150 was merged. If not, follow up.
- **Full test run with .venv**: Run `PYTHONPATH=. .venv/bin/pytest` in a proper environment to confirm `test_coaching.py` tests pass (not just collect). Watch for any logic failures in the 4 coaching tests.
- **Field discovery**: Run `scripts/clozemaster_scraper.py` with live Clozemaster credentials. Look for `"All available pairing keys for ara-eng: [...]"` in DEBUG output. Note whether `numReviewsToday`, `numSentencesDoneToday`, or similar direct card-count field appears.
- **If field found**: Add `daily_cards` column to `language_stats` table (see `attic/scripts/update_schema.py` for migration pattern), update `LanguageSyncService._update_neon_db` to store it, update `NeonSyncChecker.get_language_stats` to return it, remove the `/12` heuristic from `mcp_server.py:568`.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is the upstream. Sync via PR.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- Field discovery CANNOT be done by mecris-bot — requires live credentials. Consider running manually or building a fixture.
- `test_coaching.py` is now fixed — no longer excluded. Next session should verify tests pass (not just collect) via CI or `.venv`.
