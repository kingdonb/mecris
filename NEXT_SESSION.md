# Next Session: Resolve Review Pump unit mismatch (points vs. cards) for reviewstack

## Current Status (2026-03-27)
- **Pump Backlog Bug Fixed**: `get_language_velocity_stats` no longer sums Beeminder backlog snapshots as daily completions. Now uses `daily_completions` from Neon (numPointsToday). ✅
- **Known Residual Mismatch**: For `reviewstack`, `current_debt` and `tomorrow_liability` are in **cards**, but `daily_completions` is in **points** (numPointsToday). The Pump state classification is now meaningful but units are inconsistent.
- **Agent Loop Issue**: kingdonb/mecris#145 reports "401 error getting API key: not found" — the bot loop in both yebyen/mecris and kingdonb/mecris is broken. This is a key-management/infrastructure issue for humans, not the bot.
- **Bot Loop**: Four-skill loop (orient/plan/work/archive) is operating correctly in this session.

## Verified This Session
- [x] Root cause of Pump "always turbulent" bug: Beeminder datapoints for reviewstack/ellinika track backlog size, not completions — summing them was meaningless
- [x] Fix committed (`6304e40`): `daily_completions` from Neon used for flow rate instead of Beeminder
- [x] `get_language_stats` extended to return `daily_completions` column
- [x] All 5 review pump tests pass after fix

## Pending Verification (Next Session)
- **Residual Unit Mismatch**: For `reviewstack` (card-count goal), `daily_completions` is in points, not cards. Options: (a) add a `daily_cards` column tracked separately, (b) surface the unit difference in the MCP response so callers know, (c) accept the approximation. Needs a decision.
- **Agent Loop (kingdonb/mecris#145)**: 401 API key error in both repo loops. Requires human intervention to rotate/re-configure API keys. Not actionable by bot.
- **Upstream PR**: Consider opening a PR from yebyen/mecris → kingdonb/mecris carrying the pump fix (6304e40).

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- `daily_completions` in Neon is derived from `numPointsToday` (Clozemaster API), which may reset at Clozemaster's midnight (not necessarily US Eastern midnight).
- yebyen/mecris and kingdonb/mecris share no git common ancestor — sync is via PRs only, not git merge.
- SESSION_LOG created this session at `session_log.md`.
