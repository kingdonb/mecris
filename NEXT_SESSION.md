# Next Session: Review open epic issues (#170, #166) and decide on next feature work

## Current Status (Saturday, April 4, 2026 — session 25)
- **PR #165 MERGED** on 2026-04-04T02:25:27Z — all sessions 13–24 landed in kingdonb/mecris main.
- **yebyen/mecris == kingdonb/mecris** (0 commits ahead/behind). Repos fully in sync.
- **Session 25** delivered: 5 new pytest tests for sleep window exceptions + fuzzed dynamic cooldown logic (d58771f). Comments posted on kingdonb/mecris#162 and #130 requesting closure.
- **233 tests passing**, 2 pre-existing credential failures (test_circular_dependency, test_language_sync_service_coordination). No regressions.
- Commit `14a6d75` — test(reminders): 5 new tests for sleep window exceptions and fuzzed dynamic cooldown.

## Verified This Session
- [x] PR #165 merged — confirmed via GitHub API (`merged_at: 2026-04-04T02:25:27Z`)
- [x] yebyen/mecris in sync with kingdonb/mecris — `git rev-list --count HEAD..FETCH_HEAD` returns 0
- [x] `_calculate_dynamic_cooldown` floor: never drops below 0.75h (45 min), verified 50 runs
- [x] `_calculate_dynamic_cooldown` evening reduction: at hour=20, cooldown reduces from 4.0 to 3.4 (no fuzz)
- [x] Tier 3 fires at 3am: exempt from all sleep windows
- [x] Non-Tier-3 beeminder fires at 10pm (22:00): normal sleep but not emergency sleep → fires
- [x] Non-Tier-3 beeminder suppressed at 3am: emergency sleep window blocks it correctly
- [x] `test_tier2_escalation_resets_after_tier2_message_sent` fixed — 4.5h instead of 4.0h (dynamic cooldown ceiling = 4.25h)
- [x] Comments posted on kingdonb/mecris#162 and #130 with implementation details, requesting closure

## Pending Verification (Next Session)

### Issues to Close (Requires kingdonb)
- **kingdonb/mecris#162** — OIDC fixes implemented + merged. Comment posted. Needs kingdonb to close.
- **kingdonb/mecris#130** — Score-delta tracking implemented + merged. Comment posted. Needs kingdonb to close.
- **kingdonb/mecris#132** — "FIXED: Failover sync" — title says FIXED, still open. Needs triage/close.

### Next Feature Work (Open Epics)
After the marathon of sessions 13–24, the repo is healthy with 233 tests. Options:
- **kingdonb/mecris#170** — Epic: The Majesty Cake (Unified Goal Progress Widget) — newest epic
- **kingdonb/mecris#166** — Epic: Multi-User Twilio Accountability System (WASM Brain)
- **kingdonb/mecris#169** — Phase 3: Rust Reminder Engine (Heuristics & Multi-Tenant Dispatch)
- **kingdonb/mecris#129** — Greek Review Backlog Booster (smaller, focused)
- **kingdonb/mecris#127** — Investigate "Cloud: Failover" status in Spin App

### Live Validation (carry-forward, requires live env)
- SQL migration: `psql $NEON_DB_URL -f scripts/migrations/001_presence_table.sql`
- `get_system_health` live validation: should return `scheduler_election` rows, not error
- Ghost Archivist: `logs/ghost_archivist.log` should accumulate PULSE entries

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **Test command**: `PYTHONPATH=. .venv/bin/pytest` (with SQLAlchemy, mcp, apscheduler, cryptography installed)
- **Pre-existing failures**: `test_circular_dependency` (mock not called — credential issue) and `test_language_sync_service_coordination` (Beeminder credentials not in env). Not regressions.
- **GITHUB_TOKEN scope**: Fine-grained PAT for yebyen/mecris only. **Use GITHUB_CLASSIC_PAT** for cross-repo operations (comment on kingdonb/mecris issues). Cannot close issues on kingdonb/mecris — requires kingdonb.
- **Nag Ladder tier semantics**:
    - Tier 1: WhatsApp Template (Gentle)
    - Tier 2: WhatsApp Freeform (Escalated, 6h idle)
    - Tier 3: WhatsApp Freeform High Urgency (Critical, runway < 2.0 hours — strictly less than)
    - Tier 3 exempt from ALL sleep windows; non-Tier-3 emergencies exempt from normal sleep (8pm-8am) but blocked during emergency sleep (midnight-8am)
- **Dynamic cooldown**: `_calculate_dynamic_cooldown(base, hour)` — reduces 0.15h per hour past 4pm, fuzz ±0.25h, floor 0.75h. Applied to: arabic_review_reminder (base=2.0h), beeminder_emergency (base=4.0h).
- **`uv` not available in CI**: Use `python3 -m venv .venv && .venv/bin/pip install`.
- **Scheduler election tests**: `tests/test_scheduler_election.py` requires psycopg2 + Neon DB — skip in CI.
- **Presence table**: Schema in `scripts/migrations/001_presence_table.sql`. Must be applied to live Neon DB.
- **HealthChecker service**: `services/health_checker.py` — stale threshold: 90 seconds.
