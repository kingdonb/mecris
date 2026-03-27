# Next Session: Verify numReviewsToday field with live Clozemaster credentials (requires human or prod env)

## Current Status (2026-03-27)
- **Field discovery still blocked**: `scripts/clozemaster_scraper.py` has DEBUG logging (commit `6135f95`), but running it requires live Clozemaster credentials unavailable in the bot environment. No progress is possible here without credentials or a fixture.
- **Arabic heuristic clarified**: `mcp_server.py:568` divides `daily_completions` by 12. Comment updated (commit `9c9e8fc`) to document the dual-path reality: Python sync stores points (primary path), Rust failover sync pre-converts to cards. Heuristic is correct for the primary path.
- **Potential double-divide risk documented**: If Rust failover ran last and Python then reads from Neon, the `/12` is applied to cards instead of points. In practice, Python overwrites Rust values on next sync (points > cards numerically), so risk is low.
- **Repos in sync**: Both yebyen/mecris and kingdonb/mecris are at `9c9e8fc` (or equivalent — last sync confirmed 2026-03-27T17:58Z at `9abbfd2`).

## Verified This Session
- [x] `mcp_server.py:559` comment updated to reflect dual-path unit reality (commit `9c9e8fc`).
- [x] `tests/test_clozemaster_idempotency.py` still passes 2/2 after the comment-only change.
- [x] Rust `lib.rs:414-417` applies `/12` before writing to Neon for Arabic (read-confirmed, not changed).
- [x] Python `LanguageSyncService._update_neon_db` stores raw points (no conversion) — confirmed by reading `services/language_sync_service.py`.

## Pending Verification (Next Session)
- **Field discovery**: Run `scripts/clozemaster_scraper.py` with `logging.DEBUG` enabled (e.g., set `logging.basicConfig(level=logging.DEBUG)` at top of script temporarily). Look for `"All available pairing keys for ara-eng: [...]"` in output. Note whether `numReviewsToday`, `numSentencesDoneToday`, or similar direct card-count field appears.
- **If field found**: Add `daily_cards` column to `language_stats` table (see `attic/scripts/update_schema.py` for migration pattern), update `LanguageSyncService._update_neon_db` to store it, update `NeonSyncChecker.get_language_stats` to return it, remove the `/12` heuristic from `mcp_server.py:568`.
- **Sync PR to kingdonb**: yebyen/mecris has commit `9c9e8fc` that kingdonb/mecris does not yet have. Open a PR when ready.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is the upstream. Sync via PR.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- Field discovery CANNOT be done by mecris-bot — requires live credentials. Consider running manually or building a fixture.
