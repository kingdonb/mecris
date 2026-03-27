# Next Session: Resolve Agent Loop 401 Error and Publish Skills

## Current Status (2026-03-27)
- **Review Pump Unit Mismatch Resolved**: `get_language_velocity_stats` now handles the card-to-points mismatch for `reviewstack`. 1 card ≈ 12 points heuristic applied for Arabic. ✅
- **Pump Units Surfaced**: `ReviewPump` status now includes the unit ("cards" or "points"). ✅
- **Agent Loop Issue**: kingdonb/mecris#145 reports "401 error getting API key: not found" — the bot loop in both yebyen/mecris and kingdonb/mecris is broken. Requires human intervention to rotate/re-configure API keys.
- **Bot Governor**: Actual limit is 200 turns, documented limit is 80 turns. Planning and TDG are mandatory. ✅

## Verified This Session
- [x] `ReviewPump` unit support and status output.
- [x] Heuristic conversion for Arabic (12 pts = 1 card) in `mcp_server.py`.
- [x] TDG for all code changes (ReviewPump, mcp_server).
- [x] Sync to both `yebyen` and `kingdonb` remotes.

## Pending Verification (Next Session)
- **Agent Loop (kingdonb/mecris#145)**: 401 API key error in both repo loops. Requires human intervention to rotate/re-configure API keys.
- **Skills Discoverability**: Confirm if skills are discoverable in a standard Claude Code install.
- **Long-term**: Consider adding a `numReviewsToday` (cards) field to the scraper and Neon DB to replace the heuristic.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris and kingdonb/mecris share a common git ancestor (`66e6478`). Sync is maintained via dual-pushes.
- SESSION_LOG updated this session at `session_log.md`.
