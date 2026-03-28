# Next Session: Await kingdonb review/merge of PR #152 (slug fix + Greek Backlog Booster)

## Current Status (2026-03-28)
- **kingdonb/mecris#152 still open**: PR from yebyen:main → kingdonb:main. Carries all 5 commits from this session cycle (slug fix + Greek Backlog Booster). Scope documented via comment at #issuecomment-4148873138.
- **pr-test ✅ passed**: Run 23695038150 completed with `success`. Python tests (96) and Android tests passed against PR #152.
- **No PR #153 needed**: Previous session planned to open PR #153, but #152 already points at yebyen:main HEAD (`ce10640`) — all commits included. NEXT_SESSION item is resolved.
- **kingdonb/mecris#128 and #129**: Both will auto-close when kingdonb merges PR #152 (comment body says `Closes #128` and `Closes #129`).

## Verified This Session
- [x] PR #152 scope comment posted: slug fix + booster, closes #128 and #129
- [x] pr-test dispatched and completed: ✅ success (run 23695038150)
- [x] No new PR needed — #152 already carries all 5 commits
- [x] All 96 tests pass (Python + Android) per pr-test CI

## Pending Verification (Next Session)
- **kingdonb/mecris#152 merged?**: Check if kingdonb has merged. If yes, #128 and #129 should be closed. If still open, no action needed — leave it for kingdonb to review.
- **Post-merge sync**: After #152 merges, yebyen/mecris will be behind kingdonb/mecris temporarily. Next session should sync forward from upstream.
- **Live validation**: When `num_next_7_days` for GREEK exceeds 300 in production Neon data, confirm narrator context shows `greek_backlog_boost: true`. This requires live MCP server access — not testable in bot environment.
- **Coaching priority loop pre-existing bug**: The existing priority loop uses uppercase keys (`ARABIC`, `GREEK`) which never match lowercase DB keys. This is a known pre-existing bug, not introduced in this session. Tracked as technical debt; do not conflate with booster work.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR.
- yebyen/mecris is 5 commits ahead of kingdonb/mecris main (`b453b7e`). PR #152 carries all 5.
- `next_7_days` key is populated by `neon_sync_checker.get_language_stats()` (column `next_7_days_reviews` in Neon `language_stats` table — no schema change needed).
- Plan issue: yebyen/mecris#23 (closed this session).
