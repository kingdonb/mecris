# Next Session: The Holy Grail — Python-Native WASM & Arabic Emergency

## Current Status (Monday, March 30, 2026)
- **PR #156 OPEN**: kingdonb/mecris#156 (Logic Vacuuming Phase 0) awaiting merge.
- **Phase 1 COMPLETE**: `ReviewPump` Rust crate merged locally (17 tests ✅).
- **Architectural Shift**: Issue #157 opened to prioritize **Python-Native WASM**. We want to stop manual translation to Rust and start using existing Python logic directly in the WASM Brain.
- **ARABIC EMERGENCY**: The `reviewstack` goal (2,426 cards) derails **TODAY**. This is the highest priority for the next session.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] Helix Balance Experiment: Spent $0.45. Confirmed Qwen/Native ($0) vs Proxied ($$$).
- [x] Logic Vacuuming Phase 1: ReviewPump ported to Rust and verified with 17 tests.
- [x] Issue #157: "The Holy Grail" requirement documented.

## Pending Verification (Next Session)
- **CLEAR ARABIC BACKLOG**: Act now to prevent derailment of the `reviewstack` goal.
- **Python-in-WASM POC**: Research `componentize-py` or similar to move `BudgetGovernor` or `ReminderService` to WASM *without* rewriting in Rust.
- **WASM compile verification**: Verify `review-pump` WASM build in deployment CI.
- **Issue #122** (Android multiplier race) — still unaddressed.
- **Helix balance discovery**: `get_helix_balance()` still unvalidated against live Helix API.
- **Live sync verification**: Verify next Clozemaster sync correctly records `cards_today` in `language_stats` for Arabic.
- **Issue #122** (Android multiplier race) — still unaddressed. Needs Android UI work.
- **Issue #132** ("FIXED:" in title but still open) — needs live Spin/Neon verification to close.
- **Merge PR #156**: Still awaiting kingdonb review.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR only.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth (now also in Rust as `pub const ARABIC_POINTS_PER_CARD: i32 = 16;`).
- `get_language_stats()` stores keys as `row[0].lower()`.
- `BudgetGovernor(spend_log_path="mecris_spend_log.json")` is now active.
- `get_narrator_context()` includes `budget_governor.routing_recommendation`.
- `budget_gate()` now returns warning dict for "defer" (`budget_halted: False`); returns error dict for "deny" (`budget_halted: True`); returns `None` for "allow".
- MCP handler pattern: `if guard and guard.get("budget_halted"): return guard`
- Logic Vacuuming: ReviewPump is Phase 1 ✅ DONE. BudgetGovernor is Phase 2 (KV store + outbound HTTP). See `docs/LOGIC_VACUUMING_CANDIDATES.md`.
- `review-pump` WASM build: `cargo build --target wasm32-wasip1 --release --features spin` in `mecris-go-spin/review-pump/`. Native unit tests: `cargo test` (no features needed).
