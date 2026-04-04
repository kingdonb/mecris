# Next Session: Majesty Cake Phase 3 — Android widget integration or narrator context polish

## Current Status (Saturday, April 4, 2026 — session 27)
- **get_daily_aggregate_status** surfaced in `get_narrator_context` as `daily_aggregate_status` key (commit `6de9d2b`). Callers no longer need a separate MCP tool call.
- **Recommendation auto-appended**: "🎂 Majesty Cake!" on all_clear=True; "🎯 Daily goals progress: X/Y" otherwise. Implemented in `mcp_server.py:299-309`.
- **4 new tests** in `tests/test_narrator_aggregate_integration.py` — all passing. Total: 245 passing, 1 pre-existing failure (`test_language_sync_service_coordination` — Beeminder credentials not in env).
- **yebyen/mecris == kingdonb/mecris** (0 commits ahead/behind). Single commit added this session.
- **Plan issue yebyen/mecris#86** — closed ✅ this session.

## Verified This Session
- [x] `get_daily_aggregate_status` called from `get_narrator_context` at `mcp_server.py:299`
- [x] `daily_aggregate_status` key present in `get_narrator_context` return dict
- [x] Recommendation appended when partial: "🎯 Daily goals progress: X/Y — keep going!"
- [x] Recommendation appended when all_clear: "🎂 Majesty Cake! All daily goals complete (X/Y)"
- [x] Exception in `get_daily_aggregate_status` caught gracefully — narrator context still returns
- [x] Error result from `get_daily_aggregate_status` skips recommendation (no crash)
- [x] 4/4 tests passing in `tests/test_narrator_aggregate_integration.py`
- [x] No regressions (245 passing, same 1 pre-existing failure)

## Pending Verification (Next Session)

### Issues to Close (Requires kingdonb)
- **kingdonb/mecris#162** — OIDC fixes implemented + merged. Comment posted. Needs kingdonb to close.
- **kingdonb/mecris#130** — Score-delta tracking implemented + merged. Comment posted. Needs kingdonb to close.
- **kingdonb/mecris#132** — "FIXED: Failover sync" — title says FIXED, still open. Needs triage/close.

### Next Feature Work (Majesty Cake — kingdonb/mecris#170)
Phase 1 (backend endpoint) ✅ done. Phase 2 (discoverability in narrator context) ✅ done. Phase 3 options:
- **Android widget integration**: Wire the Android app's `HomeFragment` or a new widget to call `get_daily_aggregate_status` and display the X/Y counter. Show Majesty Cake animation when `all_clear=True`.
- **Narrator context polish**: Consider whether the aggregate recommendation should appear earlier in the recommendations list (currently appended last). Consider if `urgent_items` should be updated when score=0/3.
- **Endpoint discoverability in Gemini**: Verify that Gemini sessions pick up `daily_aggregate_status` from their context fetch.
- **Other epics**: kingdonb/mecris#166 (Multi-User Twilio), #169 (Rust Reminder Engine), #129 (Greek Backlog Booster)

### Live Validation (carry-forward, requires live env)
- SQL migration: `psql $NEON_DB_URL -f scripts/migrations/001_presence_table.sql`
- `get_system_health` live validation: should return `scheduler_election` rows, not error
- Ghost Archivist: `logs/ghost_archivist.log` should accumulate PULSE entries
- `get_daily_aggregate_status` live call — verify walk status reflects actual Neon DB state
- `get_narrator_context` live call — verify `daily_aggregate_status` key appears with real data

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **Test command**: `PYTHONPATH=. python3 -m pytest` (system Python) — `.venv/bin/pytest` does NOT exist in this CI env; install deps with `pip install pytest pytest-asyncio psycopg2-binary playwright beautifulsoup4 httpx ...`.
- **Pre-existing failures**: `test_language_sync_service_coordination` (Beeminder credentials not in env). NOT a regression.
- **GITHUB_TOKEN scope**: Fine-grained PAT for yebyen/mecris only. **Use GITHUB_CLASSIC_PAT** for cross-repo operations (comment on kingdonb/mecris issues). Cannot close issues on kingdonb/mecris — requires kingdonb.
- **Nag Ladder tier semantics**:
    - Tier 1: WhatsApp Template (Gentle)
    - Tier 2: WhatsApp Freeform (Escalated, 6h idle)
    - Tier 3: WhatsApp Freeform High Urgency (Critical, runway < 2.0 hours — strictly less than)
    - Tier 3 exempt from ALL sleep windows; non-Tier-3 emergencies exempt from normal sleep (8pm-8am) but blocked during emergency sleep (midnight-8am)
- **Dynamic cooldown**: `_calculate_dynamic_cooldown(base, hour)` — reduces 0.15h per hour past 4pm, fuzz ±0.25h, floor 0.75h. Applied to: arabic_review_reminder (base=2.0h), beeminder_emergency (base=4.0h).
- **`uv` not available in CI**: Use `pip install` directly.
- **Scheduler election tests**: `tests/test_scheduler_election.py` requires psycopg2 + Neon DB — skip in CI with `--ignore=tests/test_scheduler_election.py`.
- **Presence table**: Schema in `scripts/migrations/001_presence_table.sql`. Must be applied to live Neon DB.
- **get_daily_aggregate_status (module-level, line 883)**: Non-decorated version used by tests + called from `get_narrator_context`. The `@mcp.tool`-decorated version at line 719 has different return shape (`goals_met/total_goals/components`).
- **get_narrator_context now includes**: `daily_aggregate_status` key (from line-883 function); recommendation auto-appended.
