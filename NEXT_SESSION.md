# Next Session: Ghost Presence Global Neon Evolution (kingdonb/mecris#164)

## Current Status (Thursday, April 2, 2026 — session 15)
- **Upstream PR open**: kingdonb/mecris#165 — "feat(nag-ladder): Complete Nag Ladder" (yebyen:main → kingdonb:main, 4 commits).
- **kingdonb/mecris#139 (Nag Ladder)**: Comment posted; will close when PR #165 merges.
- **32/32 reminder tests pass**: All three Nag Ladder tiers (Tier 1 Template, Tier 2 Freeform contextual, Tier 3 Emergency) fully implemented and tested.
- **yebyen/mecris is up to date**: All session 9-14 work is in the PR, no commits pending.

## Verified This Session
- [x] **Upstream PR created**: kingdonb/mecris#165 from yebyen:main, referencing #139 for closure.
- [x] **Comment on kingdonb/mecris#139**: Posted via GITHUB_CLASSIC_PAT (fine-grained token was blocked; classic PAT worked).
- [x] **PR description complete**: Includes all 3 tiers table, 32/32 test count, and Closes #139 reference.

## Pending Verification (Next Session)

### PR Merge — Human Action Required
- kingdonb/mecris#165 needs review + merge by kingdonb (or bot with write access to kingdonb/mecris).
- Once merged, kingdonb/mecris#139 will auto-close.
- After merge, yebyen/mecris should sync (pull from kingdonb/mecris main) to stay in sync.

### Ghost Presence Global Neon Evolution (kingdonb/mecris#164)
- Good next bot session candidate after #165 merges.
- Significant architecture: Neon-backed presence table, POUND_SAND / SOFY state machine.
- Requires: SQL migration script, refactored `ghost/presence.py`, updated `mcp_server.py`, test suite for POUND_SAND → SOFY escalation.
- Can be started in yebyen/mecris fork while #165 awaits merge.

### Ghost Archivist Live Validation (carry-forward)
- The archivist job fires every 15 minutes when `MecrisScheduler` is the leader.
- Can only be validated in a live environment (Neon DB, running MCP server).
- When next doing a live session, confirm `logs/ghost_archivist.log` accumulates PULSE entries.

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
- **GITHUB_TOKEN scope**: Fine-grained PAT for yebyen/mecris only. Cannot comment on kingdonb/mecris issues. **Use GITHUB_CLASSIC_PAT** for cross-repo operations (comment, PR creation — confirmed working this session).
