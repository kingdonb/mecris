# Next Session: Merge kingdonb/mecris#153 (Budget Governor + Narrator Context + Persistence sync PR)

## Current Status (2026-03-29)
- **PR Open**: kingdonb/mecris#153 (yebyen→kingdonb sync) now includes `dbad4d4` (_spend_log persistence). pr-test passed for the prior head (`9a77f31`); needs re-test for new commit.
- **19 Unit Tests Pass**: `tests/test_budget_governor.py` has 19/19 green — 4 new persistence tests added.
- **_spend_log now durable**: `BudgetGovernor(spend_log_path=path)` persists spend events to JSON across restarts. In-memory default preserved for backward compat.
- **kingdonb/mecris#153 still open**: Awaiting kingdonb human review/merge. Bot cannot comment on kingdonb repo (fine-grained token scope is yebyen only).

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] TDG: 4 new tests written (red→green), all 19 pass.
- [x] `_spend_log` persistence committed as `dbad4d4`.
- [x] yebyen/mecris#29 plan issue created and will be closed this archive.

## Pending Verification (Next Session)
- **Re-run pr-test for PR #153**: New commit `dbad4d4` added since last CI run. Dispatch `/mecris-pr-test 153` to confirm 19 tests still pass in CI.
- **Merge kingdonb/mecris#153**: PR is open, needs human (kingdonb) to review and merge. Bot cannot merge cross-repo PRs.
- **Helix balance discovery**: `get_helix_balance()` uses `ANTHROPIC_BASE_URL/api/v1/me` — still unvalidated against live Helix API. (Human-only; requires live env with ANTHROPIC_BASE_URL set to Helix endpoint.)
- **Issue #122** (Android multiplier race) — still unaddressed.
- **Issue #132** (Failover sync verification) — needs human to trigger failover sync from Android and verify `daily_completions` in Neon.
- **Active enforcement**: `BudgetGovernor` integrated into `usage_tracker.py` or `mcp_server.py` for live deny/defer enforcement. Currently advisory only.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR only.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth (in `services/review_pump.py`).
- `get_language_stats()` always stores keys as `row[0].lower()` — all consuming code must use lowercase keys.
- `BudgetGovernor(spend_log_path=path)` for durable spend tracking; `BudgetGovernor()` for in-memory (no path = no file I/O).
- `get_narrator_context()` includes `budget_governor.routing_recommendation` — agents should check this before choosing a provider.
- Fine-grained GITHUB_TOKEN has yebyen/mecris scope only; cannot comment/merge on kingdonb/mecris. Use GITHUB_CLASSIC_PAT for kingdonb ops where available.
