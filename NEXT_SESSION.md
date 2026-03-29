# Next Session: BudgetGovernor enforcement live; verify Arabic cards_today sync

## Current Status (2026-03-29)
- **PR #153 MERGED**: kingdonb merged Budget Governor + Narrator Context integration today.
- **Repos In Sync**: yebyen/mecris HEAD `11ac980` matches kingdonb/mecris HEAD `ea2eebb` + 1 new commit. Needs a PR sync to kingdonb.
- **BudgetGovernor Active**: `budget_gate("anthropic_api")` now guards `trigger_language_sync`, `get_coaching_insight`, `get_real_anthropic_usage`. Blocks on hard "deny" (total spent ≥ limit), not on "defer".
- **21 Unit Tests Pass**: `tests/test_budget_governor.py` — 21/21 green (19 original + 2 new gate tests).
- **Clozemaster card count**: `scripts/clozemaster_scraper.py` extracts `cards_today` via `ttmNumPlayedByDate` API field; Arabic double-normalization guard in place.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] PR #153 confirmed merged at 16:21 UTC (kingdonb/mecris#153).
- [x] `BudgetGovernor.budget_gate()` implemented — returns `None` (allow) or error dict (deny).
- [x] Guards added to `trigger_language_sync`, `get_real_anthropic_usage`, `get_coaching_insight`.
- [x] All 21 budget governor tests pass (committed `11ac980`).

## Pending Verification (Next Session)
- **Open PR to kingdonb**: yebyen/mecris has 1 new commit (`11ac980`) ahead of kingdonb/mecris. Open a sync PR.
- **Helix balance discovery**: `get_helix_balance()` still unvalidated against live Helix API.
- **Live sync verification**: Verify next Clozemaster sync correctly records `cards_today` in `language_stats` for Arabic.
- **Issue #122** (Android multiplier race) — still unaddressed.
- **Logic Vacuuming prep**: Issue #154 open, document candidates (ReviewPump, BudgetGovernor) for Rust WASM migration.
- **Issue #132** ("FIXED:" in title but still open) — needs live Spin/Neon verification to close.
- **budget_gate defer policy**: Currently ignores "defer" status. Consider whether "defer" should return a softer warning rather than proceed silently.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR only.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth.
- `get_language_stats()` stores keys as `row[0].lower()`.
- `BudgetGovernor(spend_log_path="mecris_spend_log.json")` is now active.
- `get_narrator_context()` includes `budget_governor.routing_recommendation`.
- `budget_gate()` checks "deny" status only; "defer" is ignored (proceed silently).
