# Next Session: Open PR for Logic Vacuuming Phase 1 (ReviewPump Rust crate) and run pr-test

## Current Status (2026-03-30)
- **PR #156 OPEN**: kingdonb/mecris#156 (Logic Vacuuming Phase 0 — candidate analysis doc) is still open, awaiting kingdonb review/merge.
- **Logic Vacuuming Phase 1 COMPLETE**: `mecris-go-spin/review-pump/` Rust crate committed at `30d968a`. 17 unit tests pass (`cargo test`). WIT interface and spin.toml registered at `/internal/review-pump-status`.
- **yebyen/mecris is 4 commits ahead of kingdonb/mecris** (PR #156 includes 3; new Phase 1 commit is a 4th).
- **WASM build unvalidated**: `wasm32-wasip1` target not installed in CI env. WASM compile validated in deployment CI only.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] `mecris-go-spin/review-pump/Cargo.toml` — cdylib+rlib crate, optional spin-sdk feature.
- [x] `mecris-go-spin/review-pump/src/lib.rs` — `calculate_target()`, `get_status()`, `PumpStatus`, HTTP handler (spin feature), 17 `#[test]` tests.
- [x] `mecris-go-spin/review-pump/wit/review-pump.wit` — WIT interface with integer-tenth multipliers.
- [x] `mecris-go-spin/sync-service/spin.toml` — review-pump component registered at `/internal/review-pump-status`.
- [x] `cargo test` — 17/17 pass (native x86).
- [x] Python pytest — 22 BudgetGovernor tests pass; 5 pre-existing failures in test_coaching_service.py (neon_sync_checker import issue, unrelated to Phase 1).
- [x] Plan issue yebyen/mecris#36 created and closed.

## Pending Verification (Next Session)
- **Open PR for Phase 1**: yebyen/mecris is 4 commits ahead of kingdonb/mecris. A new PR from yebyen:main → kingdonb:main should be opened (or PR #156 should be merged first if kingdonb reviews it). Decide: wait for #156 merge and then open Phase 1 PR, or open a new Phase 1 PR now.
- **WASM compile verification**: After PR is merged and deployed, verify `cargo build --target wasm32-wasip1 --release --features spin` in `mecris-go-spin/review-pump/`. Target must be installed: `rustup target add wasm32-wasip1`.
- **Spin integration test**: `curl -X POST https://<spin-host>/internal/review-pump-status -d '{"debt":140,"tomorrow_liability":50,"daily_completions":55,"multiplier_x10":20,"unit":"points"}'` should return `{"status":"laminar","target_flow_rate":60,...}`.
- **Logic Vacuuming Phase 2**: Port BudgetGovernor core envelope to Rust. KV store spend log, outbound HTTP for Helix balance. See `docs/LOGIC_VACUUMING_CANDIDATES.md`.
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
