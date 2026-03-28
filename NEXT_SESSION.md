# Next Session: Open sync PR #153 to kingdonb/mecris carrying Greek Backlog Booster

## Current Status (2026-03-28)
- **kingdonb/mecris#152 still open**: Sync PR from yebyen:main → kingdonb:main (Greek slug fix + regression test). Awaiting kingdonb review/merge.
- **kingdonb/mecris#129 IMPLEMENTED**: Greek Review Backlog Booster is live in yebyen/mecris (commit `ec054ba`). `GREEK_BACKLOG_THRESHOLD = 300`, `_greek_backlog_active()`, `greek_backlog_boost` + `greek_backlog_cards` in narrator context, Priority 1 (Boost) in coaching priority loop.
- **8 new tests in `tests/test_greek_backlog_booster.py`**: 8/8 pass (threshold boundary + edge cases).
- **yebyen/mecris is 4 commits ahead of kingdonb/mecris main**: PR #152 carries commits through `3ac611e`; new commit `ec054ba` is on top.
- **kingdonb/mecris#128 still open**: Depends on PR #152 merge; owner should close after.

## Verified This Session
- [x] Greek Backlog Booster implemented: `GREEK_BACKLOG_THRESHOLD = 300` in `services/language_sync_service.py`
- [x] `_greek_backlog_active(lang_stats)` static method: reads `next_7_days` from lowercase `"greek"` key (or `"GREEK"` fallback)
- [x] `get_narrator_context` now fetches `lang_stats` via `neon_checker.get_language_stats()` and exposes `greek_backlog_boost: bool` + `greek_backlog_cards: int`
- [x] `coaching_service.py` Priority 1 (Boost): when boost active, pushes Greek ahead of Arabic unless Arabic `safebuf < 2`
- [x] `_handle_greek_backlog_boost()` method added with backlog-alert messages
- [x] 8/8 tests pass in `tests/test_greek_backlog_booster.py`
- [x] All 16 tests pass across `test_greek_backlog_booster.py`, `test_review_pump_units.py`, `test_greek_slug.py`
- [x] Syntax check clean for all modified files

## Pending Verification (Next Session)
- **Open sync PR #153**: yebyen/mecris is now 4 commits ahead of kingdonb/mecris. Open a new PR from yebyen:main → kingdonb:main carrying the Greek Backlog Booster (commit `ec054ba`). PR #152 may still be open or merged — check first. If #152 is still open, check if it can be updated to include the new commit, or open a new PR.
- **Check kingdonb/mecris#152**: Was it merged? If merged, open PR #153 for the booster. If still open, kingdonb has 4 bot commits to review — consider leaving a comment to clarify the state.
- **Full test suite (88+ tests)**: Bot environment lacks full deps (twilio, mcp, etc.). Full suite passes in CI — verify via the pr-test workflow after syncing. Expected: 88 existing + 8 new = 96 tests.
- **Live validation**: When `num_next_7_days` for GREEK exceeds 300 in production Neon data, confirm narrator context shows `greek_backlog_boost: true`.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR. As of this session, yebyen/mecris is 4 commits ahead (PR #152 pending + commit `ec054ba`).
- `next_7_days` key is already populated by `neon_sync_checker.get_language_stats()` (column `next_7_days_reviews` in Neon `language_stats` table — no schema change needed).
- Note: existing coaching priority loop uses uppercase keys (`ARABIC`, `GREEK`) which never match (keys are lowercase from DB). This is a pre-existing bug not touched in this session. The new boost code correctly uses lowercase `"greek"`.
- Plan issue: yebyen/mecris#22 (closed this session).
