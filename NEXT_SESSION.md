# Next Session: Upstream PR to kingdonb/mecris + Ghost Archivist Live Validation

## Current Status (Thursday, April 2, 2026 — session 14)
- **Nag Ladder COMPLETE (all three tiers)**: Tier 1 (WhatsApp Template), Tier 2 (WhatsApp Freeform, 6h idle, contextual for all reminder types), Tier 3 (WhatsApp Freeform High Urgency, runway < 2h).
- **32/32 reminder tests PASS**: includes 4 new Tier 3 coverage tests (cooldown, 2.0h boundary, _parse_runway_hours unit tests).
- **kingdonb/mecris#139 (Nag Ladder)**: Fully implemented in yebyen/mecris; upstream comment blocked (token scope). Pending upstream PR to close.
- **yebyen/mecris is 3 commits ahead of kingdonb/mecris**: session 13 (2b18381) + session 14 feat (bcd9469) + session 14 archive pending push.

## Verified This Session
- [x] **Tier 3 already present**: `beeminder_emergency_tier3` path exists at `services/reminder_service.py:123-139`.
- [x] **Tier 3 cooldown test**: `test_tier3_on_cooldown_returns_should_send_false` — < 1h since last → `should_send=False`.
- [x] **2.0h exact boundary**: `test_tier3_not_triggered_for_exactly_2h_runway` — "2.0 hours" falls through to `beeminder_emergency` (tier 1).
- [x] **_parse_runway_hours unit tests**: "1.5 hours" → 1.5, "0 days" → 999.0, empty → 999.0, missing key → 999.0.
- [x] **All 32 tests pass** (up from 29).

## Pending Verification (Next Session)

### Ghost Archivist Live Validation (carry-forward)
- The archivist job fires every 15 minutes when `MecrisScheduler` is the leader.
- Can only be validated in a live environment (Neon DB, running MCP server).
- When next doing a live session, confirm `logs/ghost_archivist.log` accumulates PULSE entries.

### Upstream PR (carry-forward — higher priority now)
- Sessions 9-14 add ghost/presence, ghost/archivist, scheduler integration, Tier 2 coaching copy (all types), Arabic Tier 2 contextual copy, Tier 3 test coverage.
- kingdonb/mecris#139 (Nag Ladder) can be closed once these commits are upstreamed.
- GITHUB_TOKEN (yebyen only) cannot comment on kingdonb/mecris — a human session or classic PAT is needed to post the closure comment.

### kingdonb/mecris#164 — Ghost Presence Global Neon Evolution
- New issue opened today. Significant architecture — Neon-backed presence table, POUND_SAND / SOFY state machine.
- Good candidate for next bot session after upstream PR lands.

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted. Use targeted `include_pattern` or `dir_path`.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **Nag Ladder tier semantics**:
    - Tier 1: WhatsApp Template (Gentle)
    - Tier 2: WhatsApp Freeform (Escalated, 6h idle) — coaching copy fully contextual for all types
    - Tier 3: WhatsApp Freeform High Urgency (Critical, runway < 2.0 hours — strictly less than)
- **Global Rate Limit**: 2 messages per hour across ALL channels.
- **ghost/ package**: Top-level package; import as `from ghost.presence import ...` or `from ghost.archivist import run` with `PYTHONPATH=.`.
- **Test command**: `PYTHONPATH=. .venv/bin/pytest` (create venv with `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest-cov pytest-asyncio`).
- **`uv` not available in CI**: Use `python3 -m venv .venv && .venv/bin/pip install` instead.
- **Scheduler election tests**: `tests/test_scheduler_election.py` requires psycopg2 — these fail in the bare CI environment. Pre-existing condition, not a regression.
- **GITHUB_TOKEN scope**: Fine-grained PAT for yebyen/mecris only. Cannot comment on kingdonb/mecris issues. Use GITHUB_CLASSIC_PAT for cross-repo operations.
