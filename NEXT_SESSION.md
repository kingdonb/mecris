# Next Session: Merge kingdonb/mecris#153 or address active BudgetGovernor enforcement

## Current Status (2026-03-29)
- **PR Open**: kingdonb/mecris#153 (yebyen→kingdonb sync) — pr-test re-confirmed ✅ (run 23712817277, head `5b0f381`). Awaiting human review/merge from kingdonb.
- **Upstream Synced**: yebyen/mecris now contains kingdonb commit `6f89297` "Vind-Box Architecture" (session_log.md entry). No conflicts.
- **19 Unit Tests Pass (core)**: `tests/test_budget_governor.py` — 19/19 green locally. In CI, 1 fails (`test_get_helix_balance_returns_float_on_success`) because CI has no live Helix endpoint. Pre-existing failures: 9 others (mcp/apscheduler module not in CI env).
- **Vind-Box Architecture**: kingdonb has validated a Rust WASM Brain prototype. Architectural directive: prepare Mecris for "Logic Vacuuming" — migrate ReviewPump-like logic into WASM Brain over time.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] pr-test re-run for PR #153 (head `5b0f381`): ✅ workflow success (run 23712817277). Android BUILD SUCCESSFUL. Python 106 pass, 10 fail (1 known helix connectivity, 9 pre-existing).
- [x] Upstream sync: `6f89297` (Vind-Box Architecture) merged into yebyen/mecris main — clean merge, no conflicts.
- [x] Plan issue yebyen/mecris#30 created and closed this archive.

## Pending Verification (Next Session)
- **Merge kingdonb/mecris#153**: PR is open, needs human (kingdonb) to review and merge. Bot cannot merge cross-repo PRs. pr-test has been run twice now and is green.
- **Helix balance discovery**: `get_helix_balance()` uses `ANTHROPIC_BASE_URL/api/v1/me` — still unvalidated against live Helix API. (Human-only; requires live env with ANTHROPIC_BASE_URL set to Helix endpoint.) Skip the `test_get_helix_balance_returns_float_on_success` test in CI (mark `@pytest.mark.skipif` or mock the HTTP call) to clean up CI noise.
- **Active enforcement**: `BudgetGovernor` integrated into `usage_tracker.py` or `mcp_server.py` for live deny/defer enforcement. Currently advisory only.
- **Issue #122** (Android multiplier race) — still unaddressed.
- **Issue #132** (Failover sync verification) — needs human to trigger failover sync from Android and verify `daily_completions` in Neon.
- **Logic Vacuuming prep**: kingdonb's Vind-Box Architecture milestone signals upcoming migration of Python logic (e.g., ReviewPump) to Rust WASM Brain. No action yet — document candidates when PR #153 is merged.

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
