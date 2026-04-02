# Next Session: Nag Ladder Tier 2 — Complete. Consider Tier 2 for Arabic Review Reminder.

## Current Status (Thursday, April 2, 2026 — session 12)
- **Nag Ladder Tier 2 coaching copy: COMPLETE** ✓: `_build_tier2_message()` added to `ReminderService`; walk_reminder Tier 2 now references Boris & Fiona + hours idle; beeminder_emergency Tier 2 references specific goal title + hours idle.
- **28/28 reminder tests PASS**: includes 3 new Tier 2 message content tests.
- **kingdonb/mecris#163 (PR-Test Fix) is MERGED**: PAT blocker resolved — no further action needed.
- **Repos**: yebyen/mecris is ahead of kingdonb/mecris (sessions 9+10+11+12 not yet upstreamed; push handled by workflow).

## Verified This Session
- [x] **_build_tier2_message**: walk_reminder path → "Still no walk after Nh. Boris and Fiona are not impressed. Get outside NOW."
- [x] **_build_tier2_message**: beeminder_emergency path → "ESCALATED: '{goal_title}' still at risk after Nh of silence."
- [x] **_build_tier2_message**: generic fallback path → "Escalated reminder after Nh idle: take action NOW."
- [x] **_apply_tier2_escalation**: sets `fallback_message` to the escalated copy on promotion to Tier 2.
- [x] **All 25 existing tests continue to pass** (backward-compatible change).

## Pending Verification (Next Session)

### NEXT: Arabic Review Reminder — Tier 2 Path (kingdonb/mecris#139)
- The `arabic_review_reminder` Tier 1 result has `fallback_message = "🚨 Arabic reviewstack is CRITICAL — open Clozemaster and do reviews NOW!"`.
- This passes through `_apply_tier2_escalation` → promotes to Tier 2 with a new escalated message.
- However, `arabic_review_reminder` does NOT have `variables` (it uses `template_sid` + template variables), so `_build_tier2_message` will use the generic path ("Escalated reminder after Nh idle...") — not the most contextual.
- Decision needed: add a dedicated `msg_type == "arabic_review_reminder"` branch in `_build_tier2_message` that references the Arabic goal slug/title?
- Check: is there an existing test for arabic_review_reminder escalating to Tier 2 via `_apply_tier2_escalation`? (The current `skip_count >= 3` path creates `arabic_review_escalation` separately; the idle-based promotion from `arabic_review_reminder` Tier 1 may be untested.)

### Ghost Archivist Live Validation (carry-forward)
- The archivist job fires every 15 minutes when `MecrisScheduler` is the leader.
- Can only be validated in a live environment (Neon DB, running MCP server).
- When next doing a live session, confirm `logs/ghost_archivist.log` accumulates PULSE entries.

### Upstream PR (carry-forward)
- Sessions 9-12 add ghost/presence, ghost/archivist, scheduler integration, and Tier 2 coaching copy.
- These are ready to upstream to kingdonb/mecris when Kingdon wants them.

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted. Use targeted `include_pattern` or `dir_path`.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **Nag Ladder tier semantics**:
    - Tier 1: WhatsApp Template (Gentle)
    - Tier 2: WhatsApp Freeform (Escalated, 6h idle) — coaching copy now contextual
    - Tier 3: WhatsApp High Urgency (Critical, <2h runway)
- **Global Rate Limit**: 2 messages per hour across ALL channels.
- **ghost/ package**: Top-level package; import as `from ghost.presence import ...` or `from ghost.archivist import run` with `PYTHONPATH=.`.
- **Test command**: `PYTHONPATH=. .venv/bin/pytest` (create venv with `uv venv .venv && uv pip install -r requirements.txt pytest-cov pytest-asyncio`).
- **Scheduler election tests**: `tests/test_scheduler_election.py` requires psycopg2 — these fail in the bare CI environment. Pre-existing condition, not a regression.
