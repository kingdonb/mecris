# Next Session: Manual Verification — Failover Sync & Multiplier Lever

## Current Status (2026-03-27)
- **Bot Infrastructure**: Four-skill loop (orient/plan/archive/pr-test) merged to `kingdonb/mecris` via PR #143 ✅
- **Smoke Tests**: Issues #1, #2 (smoke tests) closed; issue #4 (stale plan) closed ✅
- **Failover Sync / Beeminder**: Code is merged and deployed; end-to-end test requires Android app trigger (issue #3, still open)
- **Multiplier Lever**: SQL fix applied; persistence verification requires Android app + Neon query (issue #3)
- **MCP ↔ Rust Sync**: Unverified — requires Python MCP to come back online after Rust changes

## Verified This Session
- [x] PR #143 merged to `kingdonb/mecris` (four-skill agent loop upstream)
- [x] Issues #1, #2 (smoke tests) confirmed closed
- [x] Issue #4 (stale plan) closed
- [x] NEXT_SESSION.md updated from stale 2026-03-23 to current 2026-03-27

## Pending Verification (Next Session)
- **Failover Sync → Beeminder**: Trigger Android "Failover Sync"; confirm Beeminder datapoint created with comment `"Current: X | Tomorrow: Y | 7-day: Z"`. Tracked in yebyen/mecris#3.
- **Multiplier Lever Persistence**: Set lever in Android app; verify with `SELECT pump_multiplier FROM language_stats WHERE user_id = '...' AND language_name = '...'`.
- **MCP Coaching Persistence**: Python MCP server must reflect latest `daily_completions` and `pump_multiplier` when it comes back online after Rust changes.

## Infrastructure Notes
- Cloud Cron is still **DISABLED** in `spin.toml`. Android worker is the primary trigger for failover sync when MCP is dark.
- `language_stats` table uses a composite primary key: `(user_id, language_name)`.
- **`yebyen/mecris` and `kingdonb/mecris` share no common git ancestor** — git merge/sync is structurally impossible. Contributions flow via PR only (yebyen → kingdonb).
- Skills loop (orient/plan/archive/pr-test) lives in `kingdonb/mecris`, not in `yebyen/mecris` local `.claude/skills/`. Only `mecris-archive` is locally available in this fork.
