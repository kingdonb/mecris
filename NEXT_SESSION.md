# Next Session: Review and merge kingdonb/mecris#156 (Logic Vacuuming Phase 0 PR)

## Current Status (2026-03-30)
- **PR #156 OPEN**: kingdonb/mecris#156 (Logic Vacuuming Phase 0 — candidate analysis doc) is open and pr-test passed ✅. Awaiting kingdonb review/merge.
- **pr-test run**: yebyen/mecris actions run 23727757233 — completed success. Detailed comment posted on PR by yebyen bot.
- **yebyen/mecris is 3 commits ahead of kingdonb/mecris**: `f3dbb41` (doc), `03a419a` (archive), `739f003` (merge). All in PR #156.
- **No other open issues**: kingdonb/mecris and yebyen/mecris both clean — no needs-test, pr-review, or bug labels outstanding.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] PR kingdonb/mecris#156 opened from yebyen:main → kingdonb:main.
- [x] pr-test dispatched and completed with `success` (run 23727757233).
- [x] Plan issue yebyen/mecris#35 created and closed.

## Pending Verification (Next Session)
- **Merge PR #156**: kingdonb/mecris#156 is open; needs kingdonb to review and merge. Once merged, yebyen/mecris should be synced back from upstream.
- **Logic Vacuuming Phase 1**: Port ReviewPump to Rust/Spin. New component at `mecris-go-spin/review-pump/`. WIT interface, `cargo component build`, Spin registration, unit tests. Expose as `/internal/review-pump-status`. See `docs/LOGIC_VACUUMING_CANDIDATES.md`.
- **Helix balance discovery**: `get_helix_balance()` still unvalidated against live Helix API.
- **Live sync verification**: Verify next Clozemaster sync correctly records `cards_today` in `language_stats` for Arabic.
- **Issue #122** (Android multiplier race) — still unaddressed. Needs Android UI work.
- **Issue #132** ("FIXED:" in title but still open) — needs live Spin/Neon verification to close (trigger failover sync, check Neon for non-zero `daily_completions`, check Beeminder for "Failover" comment).

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`.
- yebyen/mecris is the bot's working fork; kingdonb/mecris is upstream. Sync via PR only.
- Bot governor: 80 turns documented limit. Planning (mecris-plan) and TDG are mandatory before code changes.
- Session log at `session_log.md`.
- `ARABIC_POINTS_PER_CARD = 16` is the single source of truth.
- `get_language_stats()` stores keys as `row[0].lower()`.
- `BudgetGovernor(spend_log_path="mecris_spend_log.json")` is now active.
- `get_narrator_context()` includes `budget_governor.routing_recommendation`.
- `budget_gate()` now returns warning dict for "defer" (`budget_halted: False`); returns error dict for "deny" (`budget_halted: True`); returns `None` for "allow".
- MCP handler pattern: `if guard and guard.get("budget_halted"): return guard`
- Logic Vacuuming: ReviewPump is Phase 1 (zero host deps), BudgetGovernor is Phase 2 (KV store + outbound HTTP). See `docs/LOGIC_VACUUMING_CANDIDATES.md`.
