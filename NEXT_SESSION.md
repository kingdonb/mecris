# Next Session: Nag Ladder Tier 2 generalization complete — PR #163 still pending, pr-test fix still blocked

## Current Status (Wednesday, April 1, 2026 — session 5)
- **PR #163 OPEN**: kingdonb/mecris#163 still awaiting review/merge. No upstream activity since session 3.
- **pr-test BROKEN for fork PRs**: `pr-test.yml` fork-PR bug still undeployed. Fix is fully documented below. Blocked on MECRIS_BOT_CLASSIC_PAT `workflow` scope (kingdonb must update).
- **Nag Ladder Tier 2 generalization DONE**: `_apply_tier2_escalation()` added to `ReminderService`. Any Tier 1 result (walk_reminder, beeminder_emergency, arabic_review_reminder) escalates to Tier 2 (`use_template: False`) after `TIER2_IDLE_HOURS = 6.0h` idle time, detected via `log_provider` message history. Committed 3a34478. (yebyen/mecris#59 closed.)
- **yebyen/mecris main** is now 6 commits ahead of kingdonb/mecris (3a34478 + 5 prior commits).
- **Zero open issues** on yebyen/mecris (yebyen/mecris#59 closed by archive).

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] PR kingdonb/mecris#163 still OPEN — no upstream review or merge activity.
- [x] `TIER2_IDLE_HOURS = 6.0` module constant in `reminder_service.py`
- [x] `_apply_tier2_escalation()` skips Tier 2/3 results; only acts on `tier == 1`
- [x] No escalation when `log_provider=None` (returns 999.0 sentinel)
- [x] No escalation when no log history (first-ever send → returns 999.0 sentinel)
- [x] `beeminder_emergency` escalates to Tier 2 after 7h idle: `tier=2`, `use_template=False`
- [x] `beeminder_emergency` stays Tier 1 when last sent 5h ago
- [x] `walk_reminder` escalates to Tier 2 after 7h idle
- [x] `sms_emergency` (Tier 3) is NOT promoted by idle-window logic (guard: `result.get("tier") != 1`)
- [x] 22/22 reminder_service tests pass (17 existing + 5 new)

## Pending Verification (Next Session)

### HIGHEST PRIORITY: Fix pr-test for fork PRs
**Requires**: MECRIS_BOT_CLASSIC_PAT updated with `repo + workflow` scopes by kingdonb.
**Fix to apply** once token is available — edit `pr-test.yml` "Fetch and merge upstream PR branch" step:
```bash
# Replace the single `git merge upstream/${PR_BRANCH}` line with:
PR_JSON=$(curl -sf -H "Authorization: Bearer ${{ secrets.MECRIS_BOT_CLASSIC_PAT }}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${UPSTREAM}/pulls/${PR}")
PR_BRANCH=$(echo "$PR_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['head']['ref'])")
HEAD_REPO=$(echo "$PR_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['head']['repo']['full_name'])")
echo "PR branch: $PR_BRANCH (head repo: $HEAD_REPO)"
git checkout -b pr-test-${PR}
if [ "$HEAD_REPO" = "yebyen/mecris" ]; then
  git fetch origin ${PR_BRANCH}
  git merge origin/${PR_BRANCH} --no-edit
else
  git merge upstream/${PR_BRANCH} --no-edit
fi
```
After applying: `git commit`, push (with workflow-scope token), re-dispatch `/mecris-pr-test 163`.

### PR #163 review/merge
- Check if kingdonb/mecris#163 has been merged.
- If merged: yebyen/mecris main will be 6 archive-only commits ahead — that's expected.
- If not merged: re-run pr-test once workflow fix is deployed.

### Nag Ladder: Tier 2 acknowledgement tracking (kingdonb/mecris#139 — next slice)
Tier 2 generalization is complete for time-based escalation. The next slice is **acknowledgement tracking**: when does the escalation reset? Currently, `_apply_tier2_escalation()` promotes after 6h idle but there's no mechanism to reset the escalation once the user acts.
- Approach: After a Beeminder goal exits CRITICAL (or walk is completed), the next `check_reminder_needed()` call naturally returns a different type or `should_send: False` — the escalation never fires because the condition is no longer met. This may be sufficient without explicit ack tracking.
- **Decision needed**: Is implicit reset (goal no longer CRITICAL) enough, or do we need explicit `last_acknowledged` per goal slug in `message_log`? File a sub-issue before coding.

### Phase 1.6 WASM build (blocked on live Spin env)
- `cd mecris-go-spin/arabic-skip-counter && spin py2wasm app -o arabic-skip-counter.wasm`
- Expected: WASM builds without errors, artifact ~43-50MB.

### Phase 1.6 live test (blocked on Spin env)
- `curl "http://localhost:3000/internal/arabic-skip-count?user_id=yebyen&hours=24"`
- Expected: `{"skip_count": <int>}`

### ARABIC BACKLOG
- `reviewstack` goal (2,426 cards) — live Beeminder status unknown. User must check manually.
- If CRITICAL, do Arabic reviews before anything else.

### Issue #122 (Android multiplier race) — still unaddressed
### Issue #132 ("FIXED:" in title) — needs live Spin/Neon verification to close

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR only.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- **CRITICAL TOKEN ISSUE**: `MECRIS_BOT_CLASSIC_PAT` secret in yebyen/mecris needs `repo + workflow` scopes to push workflow file changes. Current token has `repo` scope only. Contact kingdonb to update.
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
- **arabic_review_reminder**: Plan spec on yebyen/mecris#37. Phase 2 on yebyen/mecris#40. MCP wire-up on yebyen/mecris#41 (CLOSED). Phase 3 on yebyen/mecris#42 (CLOSED). skip_count_provider on yebyen/mecris#43 (CLOSED). Sync PR on yebyen/mecris#44 (CLOSED). componentize-py research on yebyen/mecris#45 (CLOSED). Phase 1.5a on yebyen/mecris#46 (CLOSED). Phase 1.5b on yebyen/mecris#48 (CLOSED). Phase 1.6 on yebyen/mecris#50 (CLOSED — WASM build pending in live env). Convention docs on yebyen/mecris#51 (CLOSED). PR description fix on yebyen/mecris#52 (CLOSED). Health report 2026-04-01 on yebyen/mecris#53 (CLOSED). Test coverage for today's kingdonb fixes on yebyen/mecris#55 (CLOSED). Health report 2026-04-01 session 2 on yebyen/mecris#56 (CLOSED). Upstream PR for test coverage on kingdonb/mecris#163 (OPEN — awaiting review). pr-test fork-PR bug diagnosis on yebyen/mecris#57 (CLOSED — fix identified but needs workflow-scope token). Nag Ladder Tier field + Tier 3 on yebyen/mecris#58 (CLOSED — complete, committed c4857ba). Tier 2 time-based escalation on yebyen/mecris#59 (CLOSED — complete, committed 3a34478).
- **velocity_provider API**: `ReminderService(context_provider, coaching_provider, log_provider=None, velocity_provider=None, skip_count_provider=None)`. velocity_provider called as `await velocity_provider(user_id)` → dict with key `"arabic"` containing `{"target_flow_rate": int, ...}`. skip_count_provider called as `await skip_count_provider(user_id)` → int (consecutive ignored Arabic cycles). Both fully wired in production mcp_server.py.
- **skip_count logic**: `services/arabic_skip_counter.py` uses Neon HTTP API (httpx). Counts `arabic_review_reminder` + `arabic_review_escalation` rows in `message_log` for the last 24h. SQL: `SELECT COUNT(*) FROM message_log WHERE (type = $1 OR type = $2) AND user_id = $3 AND sent_at >= $4`. Resets naturally when `reviewstack` is no longer CRITICAL.
- **Test runner in CI**: `uv` is not installed in the runner environment. Use `pip install pytest pytest-asyncio` then `PYTHONPATH=. python -m pytest` (not `.venv/bin/pytest`).
- **arabic-skip-counter test target files**: `tests/test_reminder_service.py tests/test_arabic_skip_count.py tests/test_arabic_skip_counter_component.py` (34 tests total; `test_arabic_skip_count.py` fails in CI due to missing `httpx` module — pre-existing).
- **gh CLI PR edit scope issue**: `gh pr edit` on kingdonb/mecris fails with `read:org` scope error even with GITHUB_CLASSIC_PAT (repo scope only). Use `gh api --method PATCH /repos/kingdonb/mecris/pulls/{N}` instead.
- **goal_met semantics**: When `multiplier > 1.0` and `current_debt > 0` but debt rounds to 0 daily target, `goal_met=True` (your per-day contribution is 0, so you automatically meet it). Maintenance mode (1.0x) with debt: `goal_met=False` because target=0 and multiplier is NOT > 1.0. Tests in `test_review_pump.py`.
- **get_language_stats 8-column query**: Returns `language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, pump_multiplier, daily_completions, beeminder_slug, safebuf`. Test in `test_neon_sync_checker.py`.
- **Nag Ladder tier semantics**: Tier 1 = WhatsApp template (walk_reminder, arabic_review_reminder, beeminder_emergency). Tier 2 = freeform/escalated (arabic_review_escalation, momentum_coaching; OR any Tier 1 type after 6h idle). Tier 3 = SMS emergency (sms_emergency, fires when runway string contains "hours" and < 2.0h — NOT triggered by "0 days" format). `_parse_runway_hours()` only returns sub-24h for explicit "N hours" strings. `TIER2_IDLE_HOURS = 6.0` in `reminder_service.py`.
- **_apply_tier2_escalation() API**: async helper, called at all 3 Tier 1 return sites. Guards: `result.get("tier") != 1` → passthrough. `_get_hours_since_last()` returns 999.0 when no log_provider or no history → no escalation. Escalation condition: `hours_idle < 999.0 and hours_idle >= TIER2_IDLE_HOURS`.
