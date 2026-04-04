# Next Session: Majesty Cake Phase 3 — Gemini discoverability or Android widget

## Current Status (Saturday, April 4, 2026 — session 28)
- **Recommendation ordering fixed**: Majesty Cake/aggregate rec now appears early in `get_narrator_context`. When `all_clear=True`, it is inserted at index 0 (leads the list). When partial, it appears after critical alerts (budget/Beeminder) but before walk/informational items. (`mcp_server.py:280-292`)
- **6 tests** in `tests/test_narrator_aggregate_integration.py` — all passing. Total: 247 passing, 1 pre-existing failure (`test_language_sync_service_coordination` — Beeminder credentials not in env).
- **yebyen/mecris == kingdonb/mecris** (0 commits ahead/behind after PR #171 merge). One commit added this session (`b1a4986`).
- **Plan issue yebyen/mecris#87** — closed ✅ this session.

## Verified This Session
- [x] Majesty Cake recommendation moved before walk/informational items in `get_narrator_context`
- [x] When `all_clear=True`: recommendation is inserted at index 0 (first in list)
- [x] When partial (not all_clear): recommendation appended after critical budget/Beeminder checks, before walk/groq
- [x] 6/6 tests passing in `tests/test_narrator_aggregate_integration.py`
- [x] No regressions (247 passing, same 1 pre-existing failure)

## Pending Verification (Next Session)

### Issues to Close (Requires kingdonb)
- **kingdonb/mecris#162** — OIDC fixes implemented + merged. Comment posted. Needs kingdonb to close.
- **kingdonb/mecris#130** — Score-delta tracking implemented + merged. Comment posted. Needs kingdonb to close.
- **kingdonb/mecris#132** — "FIXED: Failover sync" — title says FIXED, still open. Needs triage/close.

### Next Feature Work (Majesty Cake — kingdonb/mecris#170)
Phase 1 (backend endpoint) ✅ done. Phase 2 (discoverability in narrator context) ✅ done. Phase 3 ordering ✅ done. Phase 4 options:
- **Gemini discoverability**: Verify that Gemini sessions actually pick up `daily_aggregate_status` from their context fetch. No code change needed — just a live validation step.
- **Android widget integration**: Wire the Android app's `HomeFragment` or a new widget to call `get_daily_aggregate_status` and display the X/Y counter. Show Majesty Cake animation when `all_clear=True`.
- **Other epics**: kingdonb/mecris#166 (Multi-User Twilio), #169 (Rust Reminder Engine), #129 (Greek Backlog Booster)

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
