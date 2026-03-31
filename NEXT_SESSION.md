# Next Session: Logic Vacuuming Phase 1.6 — HTTP wrapper for arabic-skip-counter component

## Current Status (Tuesday, March 31, 2026)
- **Phase 1.5b COMPLETE**: `mecris-go-spin/arabic-skip-counter/` scaffolding committed (`db40db2`). WIT interface, `app.py`, `requirements.txt`, `.gitignore`, and 6 new unit tests.
- **componentize-py 0.21.0 builds a 43MB WASM artifact** from the Python component. Build command is now registered in `spin.toml`.
- **24/24 tests pass**: 13 `test_reminder_service.py` + 5 `test_arabic_skip_count.py` + 6 `test_arabic_skip_counter_component.py`.
- **No open issues** in yebyen/mecris or kingdonb/mecris with needs-test/pr-review/bug labels.
- **PR #159 MERGED**: kingdonb merged 2026-03-31. yebyen/mecris is fully up to date with upstream.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] PR #159 confirmed merged by kingdonb (2026-03-31T18:27Z).
- [x] `componentize-py 0.21.0` installed and produces valid WASM from Python source.
- [x] WIT world `arabic-skip-counter` compiles correctly (concrete `WitWorld` class, not ABC subclass).
- [x] `arabic-skip-counter.wasm` (43MB) produced — valid WebAssembly component module.
- [x] 6 unit tests for `WitWorld` class in `tests/test_arabic_skip_counter_component.py` — all pass.
- [x] `spin.toml` updated with `arabic-skip-counter` component entry + build command.
- [x] No regressions in existing 18 tests.

## Pending Verification (Next Session)
- **Phase 1.6**: Add HTTP trigger wrapper for `arabic-skip-counter` so it's callable as a Spin route.
  - Rewrite WIT to use WASI HTTP incoming-handler world (`wasi:http/incoming-handler@0.2.0`).
  - Route: `GET /internal/arabic-skip-count?user_id=<id>&hours=<n>` with `neon_url` from Spin variables.
  - Add `[variables]` entry in `spin.toml` for `neon_db_url`.
  - Validate with `curl` or `spin test`.
  - NOTE: This changes the WIT world structure — current function-export WIT becomes an HTTP component.
  - ALTERNATIVE: Keep current function-export WIT and call it via component-to-component linking from sync-service.
- **componentize-py class naming**: Confirmed `WitWorld` (concrete, no ABC inheritance) is correct convention. Document this in `docs/LOGIC_VACUUMING_CANDIDATES.md`.
- **Phase 1 (ReviewPump as Python component)**: `review-pump` already exists as Rust. Consider whether a Python componentize-py version is still needed or if Rust is the canonical.
- **Sync PR to kingdonb**: Open a PR from yebyen/mecris → kingdonb/mecris carrying Phase 1.5b work (`db40db2`).
- **ARABIC BACKLOG**: `reviewstack` goal (2,426 cards) — live Beeminder status unknown. User must check manually. If still CRITICAL, do Arabic reviews now.
- **Dedicated WhatsApp template for escalation**: `arabic_review_escalation` reuses `urgency_template_sid` (urgency_alert_v2). Need a dedicated template with skip count in the message. Out-of-band user work (Twilio console).
- **Live escalation wire-up verification**: Confirm that `trigger_reminder_check` returns `arabic_review_escalation` after 3 consecutive ignored cycles in production. Requires Spin app with Neon + Beeminder credentials.
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
- **componentize-py convention**: The concrete implementation class in `app.py` MUST be named `WitWorld` (same as the generated Protocol class name). Do NOT inherit from the generated abstract `WitWorld`. Define a fresh concrete class. This is the key lesson from Phase 1.5b.
- **WASM artifact size**: 43MB for this component (CPython + httpx embedded). Exceeds Fermyon free tier limit (50MB per component?) — check limits before deploying.
- `BudgetGovernor(spend_log_path="mecris_spend_log.json")` is now active.
- `get_narrator_context()` includes `budget_governor.routing_recommendation`.
- `budget_gate()` now returns warning dict for "defer" (`budget_halted: False`); returns error dict for "deny" (`budget_halted: True`); returns `None` for "allow".
- MCP handler pattern: `if guard and guard.get("budget_halted"): return guard`
- Logic Vacuuming: ReviewPump is Phase 1 (Rust, done). BudgetGovernor is Phase 2. Phase 1.5 split: 1.5a (psycopg2→httpx, DONE) and 1.5b (componentize-py WASM wrap, DONE). Phase 1.6 = HTTP wrapper. See `docs/LOGIC_VACUUMING_CANDIDATES.md`.
- **Phase 1.5a implementation detail**: Neon HTTP URL derived from postgres:// URL by parsing host, constructing `https://{host}/sql`, Basic auth = `base64(user:password)`. SQL uses OR params not ANY array.
- **Token scope**: GITHUB_TOKEN (fine-grained, yebyen/mecris only). Cannot comment on kingdonb/mecris issues. Use GITHUB_CLASSIC_PAT for workflow dispatch and cross-repo PRs.
- **arabic_review_reminder**: Plan spec on yebyen/mecris#37. Phase 2 on yebyen/mecris#40. MCP wire-up on yebyen/mecris#41 (CLOSED). Phase 3 on yebyen/mecris#42 (CLOSED). skip_count_provider on yebyen/mecris#43 (CLOSED). Sync PR on yebyen/mecris#44 (CLOSED). componentize-py research on yebyen/mecris#45 (CLOSED). Phase 1.5a on yebyen/mecris#46 (CLOSED). Phase 1.5b on yebyen/mecris#48 (CLOSED).
- **velocity_provider API**: `ReminderService(context_provider, coaching_provider, log_provider=None, velocity_provider=None, skip_count_provider=None)`. velocity_provider called as `await velocity_provider(user_id)` → dict with key `"arabic"` containing `{"target_flow_rate": int, ...}`. skip_count_provider called as `await skip_count_provider(user_id)` → int (consecutive ignored Arabic cycles). Both fully wired in production mcp_server.py.
- **skip_count logic**: `services/arabic_skip_counter.py` uses Neon HTTP API (httpx). Counts `arabic_review_reminder` + `arabic_review_escalation` rows in `message_log` for the last 24h. SQL: `SELECT COUNT(*) FROM message_log WHERE (type = $1 OR type = $2) AND user_id = $3 AND sent_at >= $4`. Resets naturally when `reviewstack` is no longer CRITICAL.
- **Test runner in CI**: `uv` is not installed in the runner environment. Use `pip install pytest pytest-asyncio` then `PYTHONPATH=. python -m pytest` (not `.venv/bin/pytest`).
