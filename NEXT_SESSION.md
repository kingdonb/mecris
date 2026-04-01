# Next Session: Phase 1.7 WASM Build Validation — Awaiting Live Spin Environment

## Current Status (Wednesday, April 1, 2026)
- **PR #161 MERGED**: kingdonb/mecris#161 (Phase 1.5b+1.6 arabic-skip-counter WASM) merged at 13:12 UTC. yebyen/mecris is fully in sync with kingdonb/mecris (identical HEAD: f62ad68 → ec4d578).
- **34/34 Python tests pass** + 3 new tests added this session (13 new passing in target files).
- **WASM build NOT run**: `spin py2wasm` and `componentize-py` unavailable in CI runner. Code is correct but unbuilt.
- **test_review_pump.py**: 2 new `goal_met` edge case tests added (5cb1397 fix coverage). Pre-existing wrong assertion fixed.
- **test_neon_sync_checker.py**: 1 new test for `get_language_stats` beeminder_slug/safebuf columns (f62ad68 fix coverage).

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] PR kingdonb/mecris#161 merged — yebyen/mecris in sync with upstream.
- [x] No open issues needing action on either kingdonb or yebyen repos.
- [x] goal_met edge case (debt rounds to zero, multiplier > 1.0) → True: covered by test.
- [x] goal_met maintenance mode with debt → False: covered by test.
- [x] get_language_stats returns beeminder_slug and safebuf: covered by test.
- [x] test_system_overdrive pre-existing wrong assertion fixed (target_flow_rate = remaining, not total).
- [x] Commit ec4d578: all 3 new tests pass, 13/13 in test_review_pump + test_neon_sync_checker.

## Pending Verification (Next Session)
- **Phase 1.6 WASM build**: In a deployment environment with `spin` CLI and `componentize-py 0.21.0`:
  ```bash
  cd mecris-go-spin/arabic-skip-counter
  pip install -r requirements.txt
  spin py2wasm app -o arabic-skip-counter.wasm
  ```
  Confirm WASM artifact builds without errors.
- **Phase 1.6 live test**: Once WASM built, start Spin app and:
  ```bash
  curl "http://localhost:3000/internal/arabic-skip-count?user_id=yebyen&hours=24"
  # Expected: {"skip_count": <int>}
  ```
- **spin_sdk API compatibility**: The `IncomingHandler.handle(self, request: Request) -> Response` signature is based on `spin-sdk>=3.0.0` docs. Verify `request.uri` attribute is correct (may be `request.url` in some versions).
- **ARABIC BACKLOG**: `reviewstack` goal (2,426 cards) — live Beeminder status unknown. User must check manually. If still CRITICAL, do Arabic reviews now.
- **Dedicated WhatsApp template for escalation**: `arabic_review_escalation` reuses `urgency_template_sid` (urgency_alert_v2). Need a dedicated template with skip count in the message. Out-of-band user work (Twilio console).
- **Issue #122** (Android multiplier race) — still unaddressed. Needs Android UI work.
- **Helix balance discovery**: `get_helix_balance()` still unvalidated against live Helix API.
- **Issue #132** ("FIXED:" in title but still open) — needs live Spin/Neon verification to close.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR only.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth (also in Rust as `pub const ARABIC_POINTS_PER_CARD: i32 = 16;`).
- `get_language_stats()` stores keys as `row[0].lower()`.
- **componentize-py conventions**: Fully documented in `docs/LOGIC_VACUUMING_CANDIDATES.md` § "componentize-py Class Naming Conventions". Short summary:
  - Function-export world → fresh concrete `WitWorld` class, no inheritance.
  - HTTP world → `IncomingHandler(spin_sdk.http.IncomingHandler)` guarded by `try/except ImportError`.
- **Phase 1.6 build command**: `spin py2wasm app -o arabic-skip-counter.wasm` (replaces old componentize-py direct invocation).
- **WASM artifact size**: 43MB for Phase 1.5b (CPython + httpx embedded). Phase 1.6 adds spin-sdk — check artifact size vs Fermyon free tier limit.
- `BudgetGovernor(spend_log_path="mecris_spend_log.json")` is now active.
- `get_narrator_context()` includes `budget_governor.routing_recommendation`.
- `budget_gate()` now returns warning dict for "defer" (`budget_halted: False`); returns error dict for "deny" (`budget_halted: True`); returns `None` for "allow".
- MCP handler pattern: `if guard and guard.get("budget_halted"): return guard`
- Logic Vacuuming: ReviewPump is Phase 1 (Rust, done). BudgetGovernor is Phase 2. Phase 1.5 split: 1.5a (psycopg2→httpx, DONE) and 1.5b (componentize-py WASM wrap, DONE). Phase 1.6 = HTTP wrapper (code done, WASM build pending). See `docs/LOGIC_VACUUMING_CANDIDATES.md`.
- **Phase 1.5a implementation detail**: Neon HTTP URL derived from postgres:// URL by parsing host, constructing `https://{host}/sql`, Basic auth = `base64(user:password)`. SQL uses OR params not ANY array.
- **Token scope**: GITHUB_TOKEN (fine-grained, yebyen/mecris only). Cannot comment on kingdonb/mecris issues. Use GITHUB_CLASSIC_PAT for workflow dispatch, cross-repo PRs, and PR edits on kingdonb/mecris.
- **arabic_review_reminder**: Plan spec on yebyen/mecris#37. Phase 2 on yebyen/mecris#40. MCP wire-up on yebyen/mecris#41 (CLOSED). Phase 3 on yebyen/mecris#42 (CLOSED). skip_count_provider on yebyen/mecris#43 (CLOSED). Sync PR on yebyen/mecris#44 (CLOSED). componentize-py research on yebyen/mecris#45 (CLOSED). Phase 1.5a on yebyen/mecris#46 (CLOSED). Phase 1.5b on yebyen/mecris#48 (CLOSED). Phase 1.6 on yebyen/mecris#50 (CLOSED — WASM build pending in live env). Convention docs on yebyen/mecris#51 (CLOSED). PR description fix on yebyen/mecris#52 (CLOSED). Health report 2026-04-01 on yebyen/mecris#53 (CLOSED). Test coverage for today's kingdonb fixes on yebyen/mecris#55 (CLOSED).
- **velocity_provider API**: `ReminderService(context_provider, coaching_provider, log_provider=None, velocity_provider=None, skip_count_provider=None)`. velocity_provider called as `await velocity_provider(user_id)` → dict with key `"arabic"` containing `{"target_flow_rate": int, ...}`. skip_count_provider called as `await skip_count_provider(user_id)` → int (consecutive ignored Arabic cycles). Both fully wired in production mcp_server.py.
- **skip_count logic**: `services/arabic_skip_counter.py` uses Neon HTTP API (httpx). Counts `arabic_review_reminder` + `arabic_review_escalation` rows in `message_log` for the last 24h. SQL: `SELECT COUNT(*) FROM message_log WHERE (type = $1 OR type = $2) AND user_id = $3 AND sent_at >= $4`. Resets naturally when `reviewstack` is no longer CRITICAL.
- **Test runner in CI**: `uv` is not installed in the runner environment. Use `pip install pytest pytest-asyncio` then `PYTHONPATH=. python -m pytest` (not `.venv/bin/pytest`).
- **arabic-skip-counter test target files**: `tests/test_reminder_service.py tests/test_arabic_skip_count.py tests/test_arabic_skip_counter_component.py` (34 tests total).
- **gh CLI PR edit scope issue**: `gh pr edit` on kingdonb/mecris fails with `read:org` scope error even with GITHUB_CLASSIC_PAT (repo scope only). Use `gh api --method PATCH /repos/kingdonb/mecris/pulls/{N}` instead.
- **goal_met semantics**: When `multiplier > 1.0` and `current_debt > 0` but debt rounds to 0 daily target, `goal_met=True` (your per-day contribution is 0, so you automatically meet it). Maintenance mode (1.0x) with debt: `goal_met=False` because target=0 and multiplier is NOT > 1.0. Tests in `test_review_pump.py`.
- **get_language_stats 8-column query**: Returns `language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, pump_multiplier, daily_completions, beeminder_slug, safebuf`. Test in `test_neon_sync_checker.py`.
