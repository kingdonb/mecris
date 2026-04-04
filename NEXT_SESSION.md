# Next Session: Continue Majesty Cake epic — phase 2 (Android integration / scoring refinement)

## Current Status (Saturday, April 4, 2026 — session 26)
- **get_daily_aggregate_status MCP tool IMPLEMENTED** in `mcp_server.py` (commit `6543fa6`). Returns `{goals, satisfied_count, total_count, all_clear, score}` for daily walk (≥2000 steps), Arabic review pump, and Greek review pump.
- **7 new tests** in `tests/test_daily_aggregate_status.py` — all passing (7/7). No regressions.
- **240 total tests** (239 passing, 3 pre-existing failures: test_circular_dependency, test_language_sync_service_coordination, test_score_delta_backup_detection_updates_daily_completions). None are regressions.
- **yebyen/mecris == kingdonb/mecris** (0 commits ahead/behind as of last sync). Single commit added this session.
- **Plan issue yebyen/mecris#84** — closed ✅ this session.

## Verified This Session
- [x] `get_daily_aggregate_status` tool registered with `@mcp.tool` in `mcp_server.py:836`
- [x] Walk goal: delegates to `get_cached_daily_activity("bike")` → `has_activity_today`
- [x] Language goals: delegates to `get_language_velocity_stats()` → `goal_met` for arabic/greek
- [x] Exception resilience: walk or language failures → goal marked unsatisfied with `error` key, other goals still evaluated
- [x] Missing language key → goal marked unsatisfied with `error: "no data"` (not crash)
- [x] 7/7 tests passing in `tests/test_daily_aggregate_status.py`
- [x] No regressions in broader suite (239 passing vs 233 pre-session, +6 net after excluding pre-existing failures)

## Pending Verification (Next Session)

### Issues to Close (Requires kingdonb)
- **kingdonb/mecris#162** — OIDC fixes implemented + merged. Comment posted. Needs kingdonb to close.
- **kingdonb/mecris#130** — Score-delta tracking implemented + merged. Comment posted. Needs kingdonb to close.
- **kingdonb/mecris#132** — "FIXED: Failover sync" — title says FIXED, still open. Needs triage/close.

### Next Feature Work (Majesty Cake — kingdonb/mecris#170)
Phase 1 (backend endpoint) is **done**. Phase 2 options:
- **Android integration**: wire the Android app to call `get_daily_aggregate_status` and display the X/Y counter widget
- **Score refinement**: the current `goal_met` logic for Arabic/Greek uses existing ReviewPump — consider whether threshold is correct for "daily pump met" vs. "pump at capacity"
- **Endpoint discoverability**: consider whether `get_daily_aggregate_status` should be called in `get_narrator_context` and surfaced in the recommendations array
- **Other epics**: kingdonb/mecris#166 (Multi-User Twilio), #169 (Rust Reminder Engine), #129 (Greek Backlog Booster)

### Live Validation (carry-forward, requires live env)
- SQL migration: `psql $NEON_DB_URL -f scripts/migrations/001_presence_table.sql`
- `get_system_health` live validation: should return `scheduler_election` rows, not error
- Ghost Archivist: `logs/ghost_archivist.log` should accumulate PULSE entries
- **New**: `get_daily_aggregate_status` live call — verify walk status reflects actual Neon DB state

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **Test command**: `PYTHONPATH=. .venv/bin/pytest` (with SQLAlchemy, mcp, apscheduler, cryptography, fastapi, playwright, requests, twilio installed in .venv)
- **Pre-existing failures**: `test_circular_dependency` (mock not called — credential issue), `test_language_sync_service_coordination` (Beeminder credentials not in env), `test_score_delta_backup_detection_updates_daily_completions` (pre-existing in this venv). Not regressions.
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
- **get_daily_aggregate_status**: New MCP tool at `mcp_server.py:836`. Composes `get_cached_daily_activity` + `get_language_velocity_stats`. No DB writes, purely read-through.
