# Next Session: Open Sync PR yebyen→kingdonb for Narrator Context Integration

## Current Status (2026-03-29)
- **Budget Governor Live in Narrator Context**: `get_narrator_context()` now returns a `budget_governor` key with `routing_recommendation` (best bucket name) and `envelope_status` (OK/HALTED). Commit `d7f3f77`.
- **15 Unit Tests Pass**: `tests/test_budget_governor.py` has 15/15 green (4 new tests for `get_narrator_summary()`).
- **yebyen/mecris ahead of kingdonb/mecris**: Commits `86c83e7`, `bbdf736`, and `d7f3f77` (Budget Governor + Narrator integration) are on yebyen only — not yet merged upstream.
- **In Sync at base**: Both repos share `dca7e37` as the pre-budget-governor baseline.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] `BudgetGovernor.get_narrator_summary()` implemented and unit-tested (15/15 pass).
- [x] `get_narrator_context()` embeds `budget_governor` key with `routing_recommendation` and `envelope_status`.
- [x] Atomic commit `d7f3f77` made and verified.

## Pending Verification (Next Session)
- **Open sync PR yebyen→kingdonb**: The narrator context integration (`d7f3f77`) plus the Budget Governor feat (`86c83e7`) need a PR to `kingdonb/mecris:main`. Open the PR and run `/mecris-pr-test <PR_NUMBER>` to confirm CI passes.
- **Helix balance discovery**: `get_helix_balance()` uses `ANTHROPIC_BASE_URL/api/v1/me` — still unvalidated against live Helix API. (Human-only; requires live env with ANTHROPIC_BASE_URL set to Helix endpoint.)
- **_spend_log persistence**: Keeper's critique: `_spend_log` is in-memory only; resets on process restart. Consider migrating to a JSON file or Neon table for cross-restart durability. Issue to open if prioritized.
- **Issue #122** (Android multiplier race) — still unaddressed.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR only.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth (in `services/review_pump.py`).
- `get_language_stats()` always stores keys as `row[0].lower()` — all consuming code must use lowercase keys.
- `BudgetGovernor` is in-memory only (no DB dependency); spend events reset on restart.
- `get_narrator_context()` now includes `budget_governor.routing_recommendation` — agents should check this before choosing a provider.
