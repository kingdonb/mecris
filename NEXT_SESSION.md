# Next Session: Review kingdonb/mecris#152 (sync PR) and implement kingdonb/mecris#129 booster

## Current Status (2026-03-28)
- **kingdonb/mecris#152 open**: Sync PR from yebyen/mecris → kingdonb/mecris carrying Greek slug pin (`3ce536e`) + regression test archive (`25de164`). Awaiting kingdonb review/merge.
- **kingdonb/mecris#128 still open**: Bot cannot close (no write access). PR #152 resolves its concern — owner should close #128 when #152 merges.
- **kingdonb/mecris#129 has spec**: Bot posted full design spec as comment at https://github.com/kingdonb/mecris/issues/129#issuecomment-4148512285. Ready to implement once PR #152 lands.
- **88/88 tests pass**: Full suite stable. No regressions.
- **Field discovery still blocked**: `scripts/clozemaster_scraper.py` requires live Clozemaster credentials unavailable in bot environment.

## Verified This Session
- [x] kingdonb/mecris#152 PR opened from yebyen:main → kingdonb/mecris:main (carries Greek slug fix + regression test)
- [x] kingdonb/mecris#129 spec comment posted with full design (backlog booster mechanism, threshold, narrator flag, priority override)
- [x] 88/88 tests still passing (no changes this session — all prior work)

## Pending Verification (Next Session)
- **Check kingdonb/mecris#152**: Was the sync PR merged? If merged, kingdonb/mecris#128 should also be closed. If still open, check for review comments and address them.
- **Implement kingdonb/mecris#129**: If #152 is merged, proceed to implement the Greek Review Backlog Booster. Spec is posted at the issue. Key tasks:
  - Add `GREEK_BACKLOG_THRESHOLD = 300` constant to `services/language_sync_service.py`
  - Add `_greek_backlog_active()` method reading `num_next_7_days` from lang_stats
  - Modify `get_narrator_context` to include `greek_backlog_boost` and `greek_backlog_cards`
  - Modify priority loop to elevate Greek when boost active (yield only to Arabic if runway < 2 days)
  - Add unit tests (mock lang_stats with num_next_7_days=350 → True; =250 → False)
  - Verify `num_next_7_days` column exists in Neon `language_stats` schema first (check kingdonb/mecris#132)

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR. As of this session, yebyen/mecris and kingdonb/mecris are 0 commits diverged pending PR #152 merge.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- Full test suite requires pyproject.toml deps (including `mcp[cli]`, `apscheduler`, `sqlalchemy`, `beautifulsoup4`, `playwright`). TDG.md build command updated accordingly in `7305a45`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth for the Arabic points-per-card constant (in `services/review_pump.py`).
- `"ellinika"` is the single source of truth for the Greek Beeminder slug (in `services/language_sync_service.py`).
- kingdonb/mecris#129 spec: booster threshold is 300 cards (`num_next_7_days`), narrator flag `greek_backlog_boost`, no Beeminder slope changes.
