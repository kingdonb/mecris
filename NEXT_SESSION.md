# Next Session: Start next meaningful epic — Greek Backlog Booster (#129) or language dashboard sorting (#121)

## Current Status (Saturday, April 4, 2026 — session 29)
- **Stale issue housekeeping complete**: Closure comments confirmed/posted on kingdonb/mecris#162, #130, #132. All three await kingdonb to click Close.
- **Android Majesty Cake widget already done**: `MajestyCakeWidget` composable (MainActivity.kt:1404-1508) was implemented in commit `db7ba41` — Phase 4 was complete before this session began.
- **6 tests** in `tests/test_narrator_aggregate_integration.py` — all passing. Total: 247 passing, 1 pre-existing failure (`test_language_sync_service_coordination` — Beeminder credentials not in env).
- **yebyen/mecris == kingdonb/mecris** (0 commits ahead/behind as of session start). Session 29 has no code changes — housekeeping only.
- **Plan issue yebyen/mecris#88** — closed ✅ this session.

## Verified This Session
- [x] kingdonb/mecris#162 — closure comment already present from session 24 ✅
- [x] kingdonb/mecris#130 — closure comment already present from session 24 ✅
- [x] kingdonb/mecris#132 — closure comment posted this session (session 29) ✅
- [x] Android MajestyCakeWidget already implemented (commit db7ba41) — no Phase 4 coding needed
- [x] `aggregateStatus` fetched via `syncApi.getAggregateStatus("Bearer $token")` at MainActivity.kt:397-400

## Pending Verification (Next Session)

### Issues to Close (Requires kingdonb)
- **kingdonb/mecris#162** — OIDC fixes implemented + merged. Comment posted. Needs kingdonb to close.
- **kingdonb/mecris#130** — Score-delta tracking implemented + merged. Comment posted. Needs kingdonb to close.
- **kingdonb/mecris#132** — "FIXED: Failover sync" — comment posted session 29. Needs kingdonb to close.

### Next Feature Work
Phase 1 (backend endpoint) ✅, Phase 2 (discoverability in narrator context) ✅, Phase 3 (ordering) ✅, Phase 4 (Android widget) ✅. Majesty Cake epic kingdonb/mecris#170 is feature-complete.

Next actionable epics (pick one):
- **kingdonb/mecris#129 — Greek Backlog Booster**: Design a mechanism to boost Greek review throughput when backlog exceeds a threshold. Scope unclear — start by reading the issue and designing an implementation approach.
- **kingdonb/mecris#121 — Language dashboard sorting**: Language stats already sorted by safebuf (MainActivity.kt:827). Re-read issue to see if there's additional sorting/visibility work still needed.
- **kingdonb/mecris#122 — Multiplier persistence race condition**: `surgicalUpdateInProgress` flag exists but review whether it fully prevents the race described in the issue.
- **Gemini discoverability live validation**: Verify Gemini sessions pick up `daily_aggregate_status`. No code change needed — requires live env.

### Live Validation (carry-forward, requires live env)
- SQL migration: `psql $NEON_DB_URL -f scripts/migrations/001_presence_table.sql`
- `get_system_health` live validation: should return `scheduler_election` rows, not error
- Ghost Archivist: `logs/ghost_archivist.log` should accumulate PULSE entries
- `get_daily_aggregate_status` live call — verify walk status reflects actual Neon DB state
- `get_narrator_context` live call — verify `daily_aggregate_status` key appears with real data AND recommendation ordering is as expected

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **Test command**: `PYTHONPATH=. python3 -m pytest` (system Python) — install deps with `pip install pytest pytest-asyncio psycopg2-binary playwright httpx fastapi uvicorn pydantic twilio flask dataclasses-json requests mcp "apscheduler>=3.11.0" "sqlalchemy>=2.0.48" "mcp[cli]>=1.26.0"`.
- **Pre-existing failures**: `test_language_sync_service_coordination` (Beeminder credentials not in env). NOT a regression.
- **GITHUB_TOKEN scope**: Fine-grained PAT for yebyen/mecris only. **Use GITHUB_CLASSIC_PAT** for cross-repo operations. Cannot close issues on kingdonb/mecris — requires kingdonb.
- **Nag Ladder tier semantics**:
    - Tier 1: WhatsApp Template (Gentle)
    - Tier 2: WhatsApp Freeform (Escalated, 6h idle)
    - Tier 3: WhatsApp Freeform High Urgency (Critical, runway < 2.0 hours — strictly less than)
    - Tier 3 exempt from ALL sleep windows; non-Tier-3 emergencies exempt from normal sleep (8pm-8am) but blocked during emergency sleep (midnight-8am)
- **Dynamic cooldown**: `_calculate_dynamic_cooldown(base, hour)` — reduces 0.15h per hour past 4pm, fuzz ±0.25h, floor 0.75h.
- **Scheduler election tests**: `tests/test_scheduler_election.py` requires psycopg2 + Neon DB — skip in CI with `--ignore=tests/test_scheduler_election.py`.
- **get_daily_aggregate_status (module-level, line 883)**: Non-decorated version used by tests + called from `get_narrator_context`. The `@mcp.tool`-decorated version at line 719 has different return shape.
- **get_narrator_context recommendation ordering** (post session 28):
    1. Large backlog warning
    2. Critical Beeminder (DERAILING)
    3. Budget constraint warning
    4. **Majesty Cake** — `insert(0, ...)` if all_clear, `append(...)` if partial (after items 1-3)
    5. Walk status (needed/not needed)
    6. Anthropic budget tracking active
    7. Groq tracking urgent
- **Android Majesty Cake widget** (MainActivity.kt:1404-1508): `MajestyCakeWidget(status = aggregateStatus)` called at line 618 of `MainNeuralDashboard`. `aggregateStatus` fetched via `syncApi.getAggregateStatus` at lines 397-400. Widget shows full 🍰 animation + golden glow on `all_clear=True`; shows X/Y score + goal icons when partial.
