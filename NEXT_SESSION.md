# Next Session: Ghost Archivist Live Validation + Upstream PR

## Current Status (Thursday, April 2, 2026 — session 13)
- **Nag Ladder Tier 2 coaching copy: FULLY COMPLETE** ✓: All three reminder types now have contextual Tier 2 escalation copy — walk_reminder (Boris & Fiona), beeminder_emergency (goal title), arabic_review_reminder (Arabic/Clozemaster context).
- **29/29 reminder tests PASS**: includes 4 Tier 2 message content tests.
- **yebyen/mecris in sync with kingdonb/mecris**: sessions 9-12 already upstreamed; session 13 commit (2b18381) pending workflow push.
- **kingdonb/mecris#139 (Arabic Reminder Tier 2)**: the implementation concern is resolved — `arabic_review_reminder` does have `variables`, and the new contextual copy is live.

## Verified This Session
- [x] **`_build_tier2_message` arabic_review_reminder branch**: returns "🚨 Arabic reviews still overdue after Nh. reviewstack won't fix itself — open Clozemaster NOW. 📚"
- [x] **`arabic_review_reminder` idle-based Tier 2 promotion**: when sent 7h ago + reviewstack CRITICAL → tier=2, use_template=False, contextual fallback (not generic).
- [x] **All 29 existing tests continue to pass** (backward-compatible change).
- [x] **NEXT_SESSION.md note corrected**: `arabic_review_reminder` does have `variables` dict (`"1"` = goal title, `"2"` = runway) — the note that it lacked variables was inaccurate.

## Pending Verification (Next Session)

### Ghost Archivist Live Validation (carry-forward)
- The archivist job fires every 15 minutes when `MecrisScheduler` is the leader.
- Can only be validated in a live environment (Neon DB, running MCP server).
- When next doing a live session, confirm `logs/ghost_archivist.log` accumulates PULSE entries.

### Upstream PR (carry-forward)
- Sessions 9-13 add ghost/presence, ghost/archivist, scheduler integration, Tier 2 coaching copy (all types), and arabic Tier 2 contextual copy.
- These are ready to upstream to kingdonb/mecris when Kingdon wants them.

### kingdonb/mecris#139 — Status
- The referenced issue tracks Arabic review reminder improvements. The Tier 2 path is now covered with contextual copy. Consider checking whether the issue needs any follow-up or can be closed upstream.

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted. Use targeted `include_pattern` or `dir_path`.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **Nag Ladder tier semantics**:
    - Tier 1: WhatsApp Template (Gentle)
    - Tier 2: WhatsApp Freeform (Escalated, 6h idle) — coaching copy fully contextual for all types
    - Tier 3: WhatsApp High Urgency (Critical, <2h runway)
- **Global Rate Limit**: 2 messages per hour across ALL channels.
- **ghost/ package**: Top-level package; import as `from ghost.presence import ...` or `from ghost.archivist import run` with `PYTHONPATH=.`.
- **Test command**: `PYTHONPATH=. .venv/bin/pytest` (create venv with `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest-cov pytest-asyncio`).
- **`uv` not available in CI**: Use `python3 -m venv .venv && .venv/bin/pip install` instead.
- **Scheduler election tests**: `tests/test_scheduler_election.py` requires psycopg2 — these fail in the bare CI environment. Pre-existing condition, not a regression.
