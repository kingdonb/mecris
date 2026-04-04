# Next Session: Start Greek Backlog Booster design (kingdonb/mecris#129)

## Current Status (Saturday, April 4, 2026 — session 30)
- **Audit session**: No code changes this session — verified two open epics are already fully implemented.
- **kingdonb/mecris#121 VERIFIED COMPLETE**: Sort-by-safebuf (line 833), alpha-dim for no-goal languages (line 861), "NO GOAL" badge (lines 881-889) all implemented. Awaiting kingdonb to close.
- **kingdonb/mecris#122 VERIFIED COMPLETE**: `surgicalUpdateInProgress` flag has 5 protection layers — early-return guard, write-site guards, click-disable, synchronous flag set, 2s settle delay. Fully prevents multiplier snap-back. Awaiting kingdonb to close.
- **249 passed** in full test suite — not re-run this session, no code changed.
- **yebyen/mecris == kingdonb/mecris** (0 commits ahead/behind as of session start).
- **Plan issues**: yebyen/mecris#90 (✅ closed) and yebyen/mecris#91 (✅ closed).

## Verified This Session
- [x] kingdonb/mecris#121 — language sort + dim already implemented in MainActivity.kt ✅
- [x] kingdonb/mecris#122 — `surgicalUpdateInProgress` fully prevents multiplier race condition ✅
- [x] Comments posted on kingdonb/mecris#121 and #122 recommending closure ✅

## Pending Verification (Next Session)

### Issues to Close (Requires kingdonb)
- **kingdonb/mecris#162** — OIDC fixes implemented + merged. Needs kingdonb to close.
- **kingdonb/mecris#130** — Score-delta tracking implemented + merged. Needs kingdonb to close.
- **kingdonb/mecris#132** — "FIXED: Failover sync" — comment posted session 29. Needs kingdonb to close.
- **kingdonb/mecris#121** — Language dashboard sorting. Bot audit confirmed complete. Needs kingdonb to close.
- **kingdonb/mecris#122** — Multiplier race condition. Bot audit confirmed complete. Needs kingdonb to close.

### Next Feature Work
- **kingdonb/mecris#129 — Greek Backlog Booster**: Read the one existing comment to understand scope, design a backlog-boost mechanism. Issue body is null — comment has the context. This is the next uncharted epic to design.

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
- **Android language dashboard** (MainActivity.kt:833): Sort order: `sortedBy { if (it.has_goal) it.safebuf else 999 }` — goals first by urgency, no-goal languages last. Alpha dim: `Modifier.alpha(0.6f)` when `!stat.has_goal`. "NO GOAL" badge at lines 881-889.
- **Android multiplier race guard** (MainActivity.kt:256, 361, 404, 417, 555, 594): `surgicalUpdateInProgress` flag — set synchronously before first suspension, checked at write-sites AND at LaunchedEffect entry, UI disabled during update, 2s settle delay post-success.
