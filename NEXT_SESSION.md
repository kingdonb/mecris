# Next Session: Merge kingdonb/mecris#153 or address active BudgetGovernor enforcement

## Current Status (2026-03-29)
- **PR Open**: kingdonb/mecris#153 (yebyen→kingdonb sync) — pr-test re-confirmed ✅ (run 23712817277, head `5b0f381`). Awaiting human review/merge from kingdonb.
- **Upstream Synced**: yebyen/mecris now contains kingdonb commit `6f89297` "Vind-Box Architecture" (session_log.md entry). No conflicts.
- **19 Unit Tests Pass (core)**: `tests/test_budget_governor.py` — 19/19 green locally. 
- **Vind-Box Architecture**: kingdonb has validated a Rust WASM Brain prototype. Architectural directive: prepare Mecris for "Logic Vacuuming" — migrate ReviewPump-like logic into WASM Brain over time.
- **Clozemaster Card Count**: Stashed work recovered — `scripts/clozemaster_scraper.py` now extracts `cards_today` via `ttmNumPlayedByDate` API field, providing accurate card counts without heuristics when available.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] pr-test re-run for PR #153 (head `5b0f381`): ✅ workflow success.
- [x] Upstream sync: `6f89297` (Vind-Box Architecture) merged.
- [x] **Stash Recovery**: `LanguageSyncService` now stores `cards_today`; `mcp_server.py` uses it to avoid Arabic double-normalization.
- [x] All local tests passing (including BudgetGovernor and ReviewPump).

## Pending Verification (Next Session)
- **Merge kingdonb/mecris#153**: PR is open, needs human review.
- **Helix balance discovery**: `get_helix_balance()` still unvalidated against live Helix API.
- **Active enforcement**: `BudgetGovernor` integrated into `usage_tracker.py` or `mcp_server.py` for live deny/defer enforcement.
- **Issue #122** (Android multiplier race) — still unaddressed.
- **Live sync verification**: Verify next sync correctly records `cards_today` in `language_stats` for Arabic.
- **Logic Vacuuming prep**: Document candidates (ReviewPump, BudgetGovernor) for migration to Rust WASM Brain.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR only.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth.
- `get_language_stats()` stores keys as `row[0].lower()`.
- `BudgetGovernor(spend_log_path="mecris_spend_log.json")` is now active.
- `get_narrator_context()` includes `budget_governor.routing_recommendation`.
