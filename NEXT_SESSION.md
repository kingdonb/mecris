# Next Session: Arabic Phase 3 MCP wire-up + PR #158 review status

## Current Status (Monday, March 30, 2026)
- **PR #158 OPEN**: kingdonb/mecris#158 — sync PR carrying `arabic_review_reminder` + WASM `anyhow` fix. Awaiting kingdonb review/merge.
- **Phase 1 COMPLETE**: `ReviewPump` Rust crate merged to main (17 tests ✅).
- **WASM Build FIXED**: `cargo build --target wasm32-wasip1 --release --features spin` exits 0.
- **Arabic Phase 2 COMPLETE (including MCP wire-up)**: `velocity_provider=get_language_velocity_stats` is now passed to `ReminderService` in `mcp_server.py`. Variable `"3"` (cards/day from ReviewPump) will be populated in `arabic_review_reminder` when `reviewstack` is CRITICAL. 10 tests pass.
- **Arabic Phase 3 COMPLETE**: `skip_count_provider` optional param added to `ReminderService`. When skip_count >= 3 and `arabic_review_escalation` cooldown (1h) has elapsed, fires `arabic_review_escalation` (more aggressive, includes skip count in var "3"). 13 tests pass (all). Committed as `c769016`.
- **ARABIC BACKLOG**: `reviewstack` goal (2,426 cards) was at derailment risk on 2026-03-30. Live status unknown — no credentials in CI. User must check Beeminder manually.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] Arabic Phase 3 escalation ladder implemented in `services/reminder_service.py`.
- [x] `skip_count_provider` (async fn → int) wired into `ReminderService.__init__` as 5th optional param.
- [x] `arabic_review_escalation` fires when skip_count >= 3, 1h cooldown, uses urgency_template_sid (same as base — dedicated template is future work).
- [x] Graceful fallback: if skip_count_provider raises, falls through to base `arabic_review_reminder`.
- [x] 3 new tests: fires after 3 ignored cycles, resets when cards_done, respects 1h cooldown.
- [x] All 13 `test_reminder_service.py` tests pass: `PYTHONPATH=. python -m pytest tests/test_reminder_service.py -v`.
- [x] Plan issue yebyen/mecris#42 created, completed, and closed.

## Pending Verification (Next Session)
- **CRITICAL: Fix Greek Data Corruption (ellinika)**: The bot incorrectly pinned the `ellinika` goal as a backlog-tracking push target. This is WRONG. `ellinika` is an odometer goal.
    - **Step 1**: In `scripts/clozemaster_scraper.py`, remove `"greek": {"slug": "ell-eng", "goal": "ellinika"}` from the `languages` dict in `sync_clozemaster_to_beeminder`.
    - **Step 2**: In `mecris-go-spin/sync-service/src/lib.rs`, change the mapping for `"ell-eng"` to return an empty Beeminder slug: `("GREEK", "")`.
    - **Step 3**: Update `tests/test_greek_slug.py` to ensure it reflects that we DO NOT push to `ellinika`.
    - **Step 4**: Verify with a dry-run that Greek is still scraped (for Neon DB stats) but NOT pushed to Beeminder.
    - **Consult Post-Mortem**: `docs/postmortems/2026-03-31-greek-data-corruption.md`.

- **PR #158 MERGED?**: Check if kingdonb has merged kingdonb/mecris#158. If merged, yebyen/mecris will need to sync back down from upstream and open a fresh sync PR for Phase 2 + Phase 3 commits.
- **MCP wire-up for skip_count_provider**: Wire an actual `skip_count_provider` implementation into `mcp_server.py` when instantiating `ReminderService`. Currently Phase 3 is in reminder_service.py but no MCP function returns a skip count. Need to either: (a) add `get_arabic_skip_count()` MCP function that reads message_log, or (b) derive skip count from `language_stats.cards_today` — if 0 and last reminder was >2h ago, increment a counter. Track in a new KV key `arabic_skip_count`.
- **Dedicated WhatsApp template for escalation**: `arabic_review_escalation` currently reuses `urgency_template_sid` (urgency_alert_v2). Need a dedicated template with a more aggressive message that incorporates skip count in a meaningful way.
- **Live Arabic status**: Check Beeminder manually — is `reviewstack` still in derailment range? If yes, do Clozemaster Arabic reviews NOW.
- **Live reminder wire-up**: Confirm `arabic_review_reminder` (with `cards_needed` in var `"3"`) appears in `message_log` after next `trigger_reminder_check` call when `reviewstack` is CRITICAL. Requires running Spin app with Neon + Beeminder credentials.
- **Python-in-WASM POC**: Research `componentize-py` or similar to move `BudgetGovernor` or `ReminderService` to WASM *without* rewriting in Rust. See kingdonb/mecris#157.
- **Issue #122** (Android multiplier race) — still unaddressed. Needs Android UI work.
- **Helix balance discovery**: `get_helix_balance()` still unvalidated against live Helix API.
- **Live sync verification**: Verify next Clozemaster sync correctly records `cards_today` in `language_stats` for Arabic.
- **Issue #132** ("FIXED:" in title but still open) — needs live Spin/Neon verification to close.

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
- **Token scope**: GITHUB_TOKEN (fine-grained, yebyen/mecris only). Cannot comment on kingdonb/mecris issues. Use GITHUB_CLASSIC_PAT for workflow dispatch and cross-repo PRs.
- **arabic_review_reminder**: Plan spec posted on yebyen/mecris#37. Phase 2 plan on yebyen/mecris#40. MCP wire-up on yebyen/mecris#41 (CLOSED). Phase 3 on yebyen/mecris#42 (CLOSED).
- **velocity_provider API**: `ReminderService(context_provider, coaching_provider, log_provider=None, velocity_provider=None, skip_count_provider=None)`. velocity_provider called as `await velocity_provider(user_id)` → dict with key `"arabic"` containing `{"target_flow_rate": int, ...}`. skip_count_provider called as `await skip_count_provider(user_id)` → int (consecutive ignored Arabic cycles). Both wired to production functions in mcp_server.py (skip_count_provider NOT YET wired — pending Phase 3 MCP wire-up).
- **Test runner in CI**: `uv` is not installed in the runner environment. Use `pip install pytest pytest-asyncio` then `PYTHONPATH=. python -m pytest` (not `.venv/bin/pytest`).
