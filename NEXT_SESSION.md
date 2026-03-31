# Next Session: Logic Vacuuming Phase 1.5b — wrap arabic_skip_counter as componentize-py WASM component

## Current Status (Tuesday, March 31, 2026)
- **PR #159 OPEN**: yebyen/mecris → kingdonb/mecris, carrying `6f73b92` (skip_count_provider wire-up) and `97d8734` (archive). Awaiting kingdonb review/merge.
- **Phase 1.5a COMPLETE**: `arabic_skip_counter.py` now uses Neon HTTP API (`httpx POST /sql`) — zero psycopg2 dependency. Committed as `296a14d`.
- **18 tests pass**: 13 `test_reminder_service.py` + 5 `test_arabic_skip_count.py` (4 rewritten + 1 new HTTP shape test).
- **Phase 1.5b READY**: arabic_skip_counter has no native-driver deps; ready for componentize-py wrapping via `fermyon/spin-python-sdk`.
- **No open issues** in yebyen/mecris or kingdonb/mecris with needs-test/pr-review/bug labels.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] PR #159 still OPEN (not merged by kingdonb as of this session).
- [x] `services/arabic_skip_counter.py` rewritten: no psycopg2, uses httpx POST to Neon /sql endpoint.
- [x] HTTP URL derived from postgres:// URL: `https://{host}/sql` + Basic auth from user:password.
- [x] SQL uses OR conditions (`type = $1 OR type = $2`) instead of `ANY(%s)` — avoids array param issues in Neon HTTP API.
- [x] 5 tests pass for arabic_skip_counter (4 rewritten, 1 new shape test).
- [x] 18/18 tests pass — no regressions in reminder_service.

## Pending Verification (Next Session)
- **PR #159 merge**: Check if kingdonb has merged kingdonb/mecris#159. If merged, yebyen/mecris will need to sync from upstream.
- **Logic Vacuuming Phase 1.5b**: Wrap `arabic_skip_counter.py` as a `componentize-py` / `spin-python-sdk` WASM component.
  - Set up `fermyon/spin-python-sdk` toolchain (install `componentize-py`, `spin` CLI).
  - Write a WIT interface for the component: exports `count-arabic-reminders: func(neon-url: string, user-id: string, hours: u32) -> u32`.
  - Bundle the component: `spin build` → `.wasm` output in `mecris-go-spin/arabic-skip-counter/`.
  - Validation: `spin build` succeeds; component can be invoked with `spin call` or unit-tested.
  - NOTE: asyncio must not be used at the WIT boundary (sync export only — already the case since `count_arabic_reminders` is sync).
- **Phase 1 (ReviewPump)**: Still not started. Pure arithmetic, no I/O — easiest WASM port. Create a new plan issue when Phase 1.5b is complete.
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
- `BudgetGovernor(spend_log_path="mecris_spend_log.json")` is now active.
- `get_narrator_context()` includes `budget_governor.routing_recommendation`.
- `budget_gate()` now returns warning dict for "defer" (`budget_halted: False`); returns error dict for "deny" (`budget_halted: True`); returns `None` for "allow".
- MCP handler pattern: `if guard and guard.get("budget_halted"): return guard`
- Logic Vacuuming: ReviewPump is Phase 1 candidate. BudgetGovernor is Phase 2. Phase 1.5 split: 1.5a (psycopg2→httpx, DONE) and 1.5b (componentize-py WASM wrap, NEXT). See `docs/LOGIC_VACUUMING_CANDIDATES.md`.
- **Phase 1.5a implementation detail**: Neon HTTP URL derived from postgres:// URL by parsing host, constructing `https://{host}/sql`, Basic auth = `base64(user:password)`. SQL uses OR params not ANY array.
- **componentize-py path**: `fermyon/spin-python-sdk` + `componentize-py`. Pure Python services (no C extensions, no asyncio at WIT boundary). arabic_skip_counter is now ready (httpx replaces psycopg2 — httpx works in WASM via Spin outbound HTTP). Binary size ~10–30MB per component.
- **Token scope**: GITHUB_TOKEN (fine-grained, yebyen/mecris only). Cannot comment on kingdonb/mecris issues. Use GITHUB_CLASSIC_PAT for workflow dispatch and cross-repo PRs.
- **arabic_review_reminder**: Plan spec posted on yebyen/mecris#37. Phase 2 plan on yebyen/mecris#40. MCP wire-up on yebyen/mecris#41 (CLOSED). Phase 3 on yebyen/mecris#42 (CLOSED). skip_count_provider MCP wire-up on yebyen/mecris#43 (CLOSED). Sync PR plan on yebyen/mecris#44 (CLOSED). componentize-py research on yebyen/mecris#45 (CLOSED). Phase 1.5a plan on yebyen/mecris#46 (CLOSED).
- **velocity_provider API**: `ReminderService(context_provider, coaching_provider, log_provider=None, velocity_provider=None, skip_count_provider=None)`. velocity_provider called as `await velocity_provider(user_id)` → dict with key `"arabic"` containing `{"target_flow_rate": int, ...}`. skip_count_provider called as `await skip_count_provider(user_id)` → int (consecutive ignored Arabic cycles). Both fully wired in production mcp_server.py.
- **skip_count logic**: `services/arabic_skip_counter.py` uses Neon HTTP API (httpx). Counts `arabic_review_reminder` + `arabic_review_escalation` rows in \`message_log\` for the last 24h. SQL: `SELECT COUNT(*) FROM message_log WHERE (type = $1 OR type = $2) AND user_id = $3 AND sent_at >= $4`. Resets naturally when `reviewstack` is no longer CRITICAL.
- **Test runner in CI**: `uv` is not installed in the runner environment. Use \`pip install pytest pytest-asyncio\` then `PYTHONPATH=. python -m pytest` (not `.venv/bin/pytest`).
ze-py research on yebyen/mecris#45 (CLOSED). Phase 1.5a plan on yebyen/mecris#46 (CLOSED).
- **velocity_provider API**: `ReminderService(context_provider, coaching_provider, log_provider=None, velocity_provider=None, skip_count_provider=None)`. velocity_provider called as `await velocity_provider(user_id)` → dict with key `"arabic"` containing `{"target_flow_rate": int, ...}`. skip_count_provider called as `await skip_count_provider(user_id)` → int (consecutive ignored Arabic cycles). Both fully wired in production mcp_server.py.
- **skip_count logic**: `services/arabic_skip_counter.py` uses Neon HTTP API (httpx). Counts `arabic_review_reminder` + `arabic_review_escalation` rows in \`message_log\` for the last 24h. SQL: `SELECT COUNT(*) FROM message_log WHERE (type = $1 OR type = $2) AND user_id = $3 AND sent_at >= $4`. Resets naturally when `reviewstack` is no longer CRITICAL.
- **Test runner in CI**: `uv` is not installed in the runner environment. Use \`pip install pytest pytest-asyncio\` then `PYTHONPATH=. python -m pytest` (not `.venv/bin/pytest`).
