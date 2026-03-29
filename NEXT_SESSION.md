# Next Session: Merge kingdonb/mecris#153 (Budget Governor + Narrator Context sync PR)

## Current Status (2026-03-29)
- **PR Open and Tested**: kingdonb/mecris#153 (yebyen→kingdonb sync) is open with `d7f3f77` and `be9107b`. pr-test ✅ passed (run 23708310760). Ready to merge.
- **15 Unit Tests Pass**: `tests/test_budget_governor.py` has 15/15 green — all Budget Governor + Narrator context tests.
- **kingdonb/mecris#144 Closed**: Budget Governor feature issue closed after CI pass.
- **`get_narrator_context()` now embeds `budget_governor`**: Returns `routing_recommendation` (best bucket) and `envelope_status` (OK/HALTED) for all agents.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] Sync PR opened: kingdonb/mecris#153 (yebyen:main → kingdonb:main).
- [x] pr-test workflow passed ✅ for PR #153 (run 23708310760).
- [x] Plan issue yebyen/mecris#28 closed with outcome.
- [x] kingdonb/mecris#144 closed (Budget Governor feature complete).

## Pending Verification (Next Session)
- **Merge kingdonb/mecris#153**: PR is open, CI is green — needs a human (kingdonb) to review and merge. Bot cannot merge cross-repo PRs with available tokens.
- **Helix balance discovery**: `get_helix_balance()` uses `ANTHROPIC_BASE_URL/api/v1/me` — still unvalidated against live Helix API. (Human-only; requires live env with ANTHROPIC_BASE_URL set to Helix endpoint.)
- **_spend_log persistence**: `_spend_log` is in-memory only; resets on process restart. Consider migrating to a JSON file or Neon table for cross-restart durability. (Keeper's critique — low urgency but noted.)
- **Issue #122** (Android multiplier race) — still unaddressed.
- **Issue #132** (Failover sync verification) — needs human to trigger failover sync from Android and verify `daily_completions` in Neon.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR only.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth (in `services/review_pump.py`).
- `get_language_stats()` always stores keys as `row[0].lower()` — all consuming code must use lowercase keys.
- `BudgetGovernor` is in-memory only (no DB dependency); spend events reset on restart.
- `get_narrator_context()` now includes `budget_governor.routing_recommendation` — agents should check this before choosing a provider.
