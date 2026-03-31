# Next Session: Open sync PR for skip_count_provider + MCP wire-up to kingdonb/mecris

## Current Status (Tuesday, March 31, 2026)
- **PR #158 MERGED**: kingdonb merged on 2026-03-31T02:32:46Z. All Arabic Phase 1-3 + WASM fix is in kingdonb/mecris main.
- **Arabic Phase 3 COMPLETE (with MCP wire-up)**: `skip_count_provider=get_arabic_skip_count` is now wired in `mcp_server.py`. `arabic_review_escalation` can fire in production when skip_count >= 3 and reviewstack CRITICAL.
- **`services/arabic_skip_counter.py`** created: testable `count_arabic_reminders(neon_url, user_id, hours=24)` queries `message_log` for consecutive Arabic reminders. Lazy psycopg2 import so CI without Neon works.
- **17 tests pass**: 13 `test_reminder_service.py` + 4 `test_arabic_skip_count.py`.
- **ARABIC BACKLOG**: `reviewstack` goal (2,426 cards) derailment risk on 2026-03-30 — live status unknown. User must check Beeminder manually.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] PR #158 confirmed MERGED (2026-03-31T02:32:46Z) — yebyen/mecris main is already synced (merge commit `db743be` in local tree).
- [x] `services/arabic_skip_counter.py` — `count_arabic_reminders()` implemented and tested.
- [x] `get_arabic_skip_count(user_id)` added to `mcp_server.py` — async wrapper using asyncio.to_thread; returns 0 if NEON_DB_URL unset.
- [x] `ReminderService` instantiation in `mcp_server.py` updated: `skip_count_provider=get_arabic_skip_count`.
- [x] All 17 tests pass: `PYTHONPATH=. python -m pytest tests/test_reminder_service.py tests/test_arabic_skip_count.py -v`.
- [x] Plan issue yebyen/mecris#43 created, completed, and closed.

## Pending Verification (Next Session)
- **Sync PR to kingdonb**: yebyen/mecris now has `6f73b92` (skip_count_provider wire-up) on top of the merged PR #158 base. Open a fresh sync PR: yebyen/mecris → kingdonb/mecris carrying this commit.
- **Dedicated WhatsApp template for escalation**: `arabic_review_escalation` reuses `urgency_template_sid` (urgency_alert_v2). Need a dedicated template with a more aggressive message that incorporates skip count in a meaningful way. This is out-of-band user work (Twilio console).
- **Live Arabic status**: Check Beeminder manually — is `reviewstack` still in derailment range? If yes, do Clozemaster Arabic reviews NOW.
- **Live escalation wire-up verification**: Confirm that `trigger_reminder_check` returns `arabic_review_escalation` type after 3 consecutive ignored cycles in production. Requires running Spin app with Neon + Beeminder credentials.
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
- **arabic_review_reminder**: Plan spec posted on yebyen/mecris#37. Phase 2 plan on yebyen/mecris#40. MCP wire-up on yebyen/mecris#41 (CLOSED). Phase 3 on yebyen/mecris#42 (CLOSED). skip_count_provider MCP wire-up on yebyen/mecris#43 (CLOSED).
- **velocity_provider API**: `ReminderService(context_provider, coaching_provider, log_provider=None, velocity_provider=None, skip_count_provider=None)`. velocity_provider called as `await velocity_provider(user_id)` → dict with key `"arabic"` containing `{"target_flow_rate": int, ...}`. skip_count_provider called as `await skip_count_provider(user_id)` → int (consecutive ignored Arabic cycles). Both fully wired in production mcp_server.py.
- **skip_count logic**: `services/arabic_skip_counter.py` counts `arabic_review_reminder` + `arabic_review_escalation` rows in `message_log` for the last 24h. Proxy for ignored cycles: each fired reminder = one cycle ignored. Resets naturally when `reviewstack` is no longer CRITICAL (cards done).
- **Test runner in CI**: `uv` is not installed in the runner environment. Use `pip install pytest pytest-asyncio` then `PYTHONPATH=. python -m pytest` (not `.venv/bin/pytest`).
