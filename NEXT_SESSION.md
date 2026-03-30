# Next Session: Open Logic Vacuuming Phase 0 PR to kingdonb/mecris

## Current Status (2026-03-29)
- **PR #155 MERGED**: kingdonb/mecris#155 (budget_gate enforcement + defer warning) merged at 2026-03-29T23:47:37Z. Working directory is at the post-merge state.
- **No open PRs or labeled issues**: kingdonb/mecris and yebyen/mecris both clean — no needs-test, pr-review, or bug labels outstanding.
- **Logic Vacuuming Phase 0 complete**: `docs/LOGIC_VACUUMING_CANDIDATES.md` committed as `f3dbb41`. Covers ReviewPump (LOW complexity, Phase 1) and BudgetGovernor (MEDIUM complexity, Phase 2) with WIT interface sketches and migration sequence.
- **22 Unit Tests Pass**: `tests/test_budget_governor.py` — 22/22 green (unchanged this session).
- **PR pending push**: The `f3dbb41` doc commit needs the workflow to push it to yebyen/mecris before a PR can be opened to kingdonb/mecris.

## Verified This Session
- [x] Identity Check: 🏛️ Canary active.
- [x] PR #155 confirmed merged into kingdonb/mecris.
- [x] No open issues in yebyen/mecris or labeled issues in kingdonb/mecris.
- [x] `docs/LOGIC_VACUUMING_CANDIDATES.md` written — ReviewPump and BudgetGovernor analysed as WASM migration candidates with WIT sketches, host dependency table, migration sequence.
- [x] Commit `f3dbb41` — `docs(logic-vacuuming): Phase 0 candidate analysis`.

## Pending Verification (Next Session)
- **Open PR `f3dbb41` → kingdonb/mecris**: After workflow pushes to yebyen/mecris, open a sync PR carrying `f3dbb41` (LOGIC_VACUUMING_CANDIDATES doc). Run pr-test. Close yebyen/mecris#34.
- **Helix balance discovery**: `get_helix_balance()` still unvalidated against live Helix API.
- **Live sync verification**: Verify next Clozemaster sync correctly records `cards_today` in `language_stats` for Arabic.
- **Issue #122** (Android multiplier race) — still unaddressed. Needs Android UI work.
- **Logic Vacuuming Phase 1**: Port ReviewPump to Rust/Spin. New component at `mecris-go-spin/review-pump/`. WIT interface, `cargo component build`, Spin registration, unit tests. Expose as `/internal/review-pump-status`.
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
