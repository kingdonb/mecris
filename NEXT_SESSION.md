# Next Session: Fix pr-test workflow (workflow scope) + re-test kingdonb/mecris#163

## Current Status (Wednesday, April 1, 2026 — session 3)
- **PR #163 OPEN**: kingdonb/mecris#163 still awaiting review/merge. No changes upstream.
- **pr-test BROKEN for fork PRs**: `pr-test.yml` always fetches PR branch from `upstream` (kingdonb/mecris). Fork PRs (head on yebyen) fail with `merge: upstream/${PR_BRANCH} - not something we can merge`. Confirmed in runs #23863414611 and #23863517252.
- **Fix identified but undeployable**: Both `GITHUB_TOKEN` and `GITHUB_CLASSIC_PAT` lack `workflow` scope required to push `.github/workflows/` files. Fix requires MECRIS_BOT_CLASSIC_PAT to be updated with `repo + workflow` scopes by kingdonb.
- **yebyen/mecris main** unchanged from session 2: still 2 commits (ec4d578 test + archive commits) ahead of kingdonb/mecris.
- **Zero open issues** on both repos (yebyen/mecris#57 will be closed by archive).

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] PR kingdonb/mecris#163 still OPEN — no upstream review or merge activity.
- [x] pr-test workflow bug reproduced and root cause confirmed: fork-origin PR branches not found in `upstream` remote.
- [x] Fix tested locally: detect `head.repo.full_name`; if `yebyen/mecris`, use `git fetch origin ${PR_BRANCH}` instead of `upstream/${PR_BRANCH}`.
- [x] Revert of workflow fix commit confirmed (412f032 reverted) — local HEAD is clean at f680093.
- [x] Blocker comment posted on kingdonb/mecris#163 explaining the token scope issue.

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
- If merged: yebyen/mecris main will be 2 archive-only commits ahead (cf4af18 + f680093) — that's expected.
- If not merged: re-run pr-test once workflow fix is deployed.

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
- **arabic_review_reminder**: Plan spec on yebyen/mecris#37. Phase 2 on yebyen/mecris#40. MCP wire-up on yebyen/mecris#41 (CLOSED). Phase 3 on yebyen/mecris#42 (CLOSED). skip_count_provider on yebyen/mecris#43 (CLOSED). Sync PR on yebyen/mecris#44 (CLOSED). componentize-py research on yebyen/mecris#45 (CLOSED). Phase 1.5a on yebyen/mecris#46 (CLOSED). Phase 1.5b on yebyen/mecris#48 (CLOSED). Phase 1.6 on yebyen/mecris#50 (CLOSED — WASM build pending in live env). Convention docs on yebyen/mecris#51 (CLOSED). PR description fix on yebyen/mecris#52 (CLOSED). Health report 2026-04-01 on yebyen/mecris#53 (CLOSED). Test coverage for today's kingdonb fixes on yebyen/mecris#55 (CLOSED). Health report 2026-04-01 session 2 on yebyen/mecris#56 (CLOSED). Upstream PR for test coverage on kingdonb/mecris#163 (OPEN — awaiting review). pr-test fork-PR bug diagnosis on yebyen/mecris#57 (CLOSED — fix identified but needs workflow-scope token).
- **velocity_provider API**: `ReminderService(context_provider, coaching_provider, log_provider=None, velocity_provider=None, skip_count_provider=None)`. velocity_provider called as `await velocity_provider(user_id)` → dict with key `"arabic"` containing `{"target_flow_rate": int, ...}`. skip_count_provider called as `await skip_count_provider(user_id)` → int (consecutive ignored Arabic cycles). Both fully wired in production mcp_server.py.
- **skip_count logic**: `services/arabic_skip_counter.py` uses Neon HTTP API (httpx). Counts `arabic_review_reminder` + `arabic_review_escalation` rows in `message_log` for the last 24h. SQL: `SELECT COUNT(*) FROM message_log WHERE (type = $1 OR type = $2) AND user_id = $3 AND sent_at >= $4`. Resets naturally when `reviewstack` is no longer CRITICAL.
- **Test runner in CI**: `uv` is not installed in the runner environment. Use `pip install pytest pytest-asyncio` then `PYTHONPATH=. python -m pytest` (not `.venv/bin/pytest`).
- **arabic-skip-counter test target files**: `tests/test_reminder_service.py tests/test_arabic_skip_count.py tests/test_arabic_skip_counter_component.py` (34 tests total).
- **gh CLI PR edit scope issue**: `gh pr edit` on kingdonb/mecris fails with `read:org` scope error even with GITHUB_CLASSIC_PAT (repo scope only). Use `gh api --method PATCH /repos/kingdonb/mecris/pulls/{N}` instead.
- **goal_met semantics**: When `multiplier > 1.0` and `current_debt > 0` but debt rounds to 0 daily target, `goal_met=True` (your per-day contribution is 0, so you automatically meet it). Maintenance mode (1.0x) with debt: `goal_met=False` because target=0 and multiplier is NOT > 1.0. Tests in `test_review_pump.py`.
- **get_language_stats 8-column query**: Returns `language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, pump_multiplier, daily_completions, beeminder_slug, safebuf`. Test in `test_neon_sync_checker.py`.
