# Next Session: Python-in-WASM POC (componentize-py research) or Arabic Phase 2

## Current Status (Monday, March 30, 2026)
- **PR #156 MERGED**: kingdonb/mecris#156 (Logic Vacuuming Phase 0) — repos now identical.
- **Phase 1 COMPLETE**: `ReviewPump` Rust crate merged to main (17 tests ✅).
- **WASM Build FIXED**: `cargo build --target wasm32-wasip1 --release --features spin` now exits 0. Fixed missing `anyhow` dep in Cargo.toml (commit `0d40606`).
- **Arabic Reminder DONE**: `arabic_review_reminder` type implemented in `services/reminder_service.py` (commit `f969dbc`). Fires every 2h (vs 4h generic) when `reviewstack` is CRITICAL. 8 tests passing.
- **ARABIC BACKLOG**: `reviewstack` goal (2,426 cards) was at derailment risk on 2026-03-30. Live status unknown — no credentials in CI runner. User must check Beeminder manually.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] PR #156 merged — yebyen/mecris == kingdonb/mecris (confirmed via GitHub API).
- [x] `arabic_review_reminder`: 3 new tests added, all 8 reminder_service tests green.
- [x] `arabic_review_reminder` fires before generic `beeminder_emergency` for `reviewstack` slug.
- [x] 2h cooldown enforced (distinct from 4h generic emergency cooldown).
- [x] **WASM compile verification**: `cargo build --target wasm32-wasip1 --release --features spin` exits 0. Root cause: `anyhow` was used in `spin_handler` module but absent from `Cargo.toml`. Fixed by adding `anyhow = { version = "1.0", optional = true }` gated under `spin` feature. All 17 native tests still pass.

## Pending Verification (Next Session)
- **LIVE ARABIC STATUS**: Check Beeminder manually — is `reviewstack` still in derailment range? If yes, do Clozemaster Arabic reviews NOW.
- **Live reminder wire-up**: Confirm `arabic_review_reminder` appears in `message_log` table after next `trigger_reminder_check` call when `reviewstack` is CRITICAL. Requires running Spin app with Neon + Beeminder credentials.
- **Python-in-WASM POC**: Research `componentize-py` or similar to move `BudgetGovernor` or `ReminderService` to WASM *without* rewriting in Rust. See kingdonb/mecris#157.
- **Issue #122** (Android multiplier race) — still unaddressed. Needs Android UI work.
- **Helix balance discovery**: `get_helix_balance()` still unvalidated against live Helix API.
- **Live sync verification**: Verify next Clozemaster sync correctly records `cards_today` in `language_stats` for Arabic.
- **Issue #132** ("FIXED:" in title but still open) — needs live Spin/Neon verification to close.
- **Arabic Phase 2**: Add cards-needed from `get_language_velocity_stats` to reminder variables; dedicated WhatsApp template; escalation ladder if reminder ignored 3+ cycles.
- **Open PR to kingdonb/mecris**: The `anyhow` Cargo.toml fix (commit `0d40606`) lives on yebyen/mecris only. Open a sync PR so upstream benefits.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR only.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth (also in Rust as `pub const ARABIC_POINTS_PER_CARD: i32 = 16;`).
- `get_language_stats()` stores keys as `row[0].lower()`.
- `BudgetGovernor(spend_log_path="mecris_spend_log.json")` is now active.
- `get_narrator_context()` includes `budget_governor.routing_recommendation`.
- `budget_gate()` now returns warning dict for "defer" (`budget_halted: False`); returns error dict for "deny" (`budget_halted: True`); returns `None` for "allow".
- MCP handler pattern: `if guard and guard.get("budget_halted"): return guard`
- Logic Vacuuming: ReviewPump is Phase 1 ✅ DONE. BudgetGovernor is Phase 2 (KV store + outbound HTTP). See `docs/LOGIC_VACUUMING_CANDIDATES.md`.
- `review-pump` WASM build: `cargo build --target wasm32-wasip1 --release --features spin` in `mecris-go-spin/review-pump/`. Native unit tests: `cargo test` (no features needed). **Target `wasm32-wasip1` must be installed**: `rustup target add wasm32-wasip1`.
- **Token scope**: GITHUB_TOKEN (fine-grained, yebyen/mecris only). Cannot comment on kingdonb/mecris issues. Use GITHUB_CLASSIC_PAT for workflow dispatch only.
- **arabic_review_reminder**: Plan spec posted on yebyen/mecris#37 (not kingdonb/mecris#125 — token scope). Recommend kingdonb add design notes to #125 after reviewing the PR.
