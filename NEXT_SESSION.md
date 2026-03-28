# Next Session: Close kingdonb/mecris#128 (awaiting owner) or pick up #122

## Current Status (2026-03-28)
- **kingdonb/mecris#128 commented**: Greek slug correction verified as pre-fixed. Comment posted at kingdonb/mecris#128 explaining the finding. Issue cannot be closed by yebyen (no write access) — owner must close.
- **Regression test added**: `tests/test_greek_slug.py` (commit `16f0727`) pins `LanguageSyncService.lang_to_slug["GREEK"] == "ellinika"` and asserts no active Python source contains `reviewstack-greek` as a hardcoded value.
- **88/88 tests pass**: Full suite (was 82/82 before this session; 3 new slug tests + 3 subtests).
- **Field discovery still blocked**: `scripts/clozemaster_scraper.py` requires live Clozemaster credentials unavailable in the bot environment.
- **kingdonb/mecris is 1 commit ahead of upstream**: Commit `16f0727` not yet in kingdonb/mecris (needs sync PR or direct merge).

## Verified This Session
- [x] kingdonb/mecris#128: `reviewstack-greek` appears ONLY in `docs/REVIEWSTACK_EXPANSION_PLAN.md` (planning doc for a future proposed goal, not a wrong slug in live code).
- [x] All active Python code uses `ellinika` as the Greek Beeminder slug.
- [x] `tests/test_greek_slug.py` 3/3 pass (committed `16f0727`).
- [x] Full suite 88/88 pass.
- [x] Comment posted on kingdonb/mecris#128 with full investigation findings.

## Pending Verification (Next Session)
- **Close kingdonb/mecris#128**: Awaiting kingdonb to close. If still open, just note it — no further action needed from bot.
- **Sync PR**: Open a PR from yebyen/mecris → kingdonb/mecris carrying commit `16f0727` (or just notify kingdonb to pull).
- **Other backlog**: kingdonb/mecris has ~20 open issues. Next candidates:
  - kingdonb/mecris#122 (Android multiplier persistence race) — Android code, requires Kotlin/Rust context
  - kingdonb/mecris#132 (Failover sync verification) — needs live Spin/Neon environment
  - kingdonb/mecris#144 (Budget governor) — large feature, multi-session
- **Field discovery**: Run `scripts/clozemaster_scraper.py` with live Clozemaster credentials. Cannot be done by bot.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is the upstream. Sync via PR.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- Full test suite requires pyproject.toml deps (including `mcp[cli]`, `apscheduler`, `sqlalchemy`, `beautifulsoup4`, `playwright`). TDG.md build command updated accordingly in `7305a45`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth for the Arabic points-per-card constant (in `services/review_pump.py`). Do not change without also checking `test_arabic_points_per_card_is_conservative`.
- `"ellinika"` is the single source of truth for the Greek Beeminder slug (in `services/language_sync_service.py`). Do not change without also updating `tests/test_greek_slug.py`.
