# Next Session: Goal 1 Phase 1 — Ghost Presence Detection

## Current Status (Wednesday, April 1, 2026 — session 8)
- **Alpha Hardening COMPLETE** ✓: All user credentials (Beeminder, Clozemaster) are now AES-256-GCM encrypted in Neon. Multi-tenancy logic is active in Python and Rust.
- **Nag Ladder ACTIVE** ✓: Tier 1/2/3 escalation logic verified. Global 2x/hour rate limit codified and passing tests.
- **Repos in sync**: yebyen = kingdonb at `ae6f311` (plus hardening commits).
- **135/135 tests PASS**: includes all multi-tenancy, Nag Ladder, and sync regression fixes.

## Verified This Session
- [x] **EncryptionService**: AES-256-GCM roundtrip verified (Python).
- [x] **Beeminder Hardening**: `BeeminderClient` loads encrypted tokens from Neon.
- [x] **Clozemaster Hardening**: `ClozemasterScraper` loads encrypted credentials from Neon.
- [x] **Data Migration**: Existing credentials moved from `.env` to encrypted DB rows.
- [x] **Global Rate Limit**: Strict 30-minute aggregate cooldown verified with tests.
- [x] **Nag Eval**: CLI confirmed working with encrypted credentials.

## Pending Verification (Next Session)

### HIGHEST PRIORITY: Goal 1 Phase 1 — Ghost Presence Detection
- **Infrastructure Ready**: Security and CLI foundations are solid.
- **Task**: Implement detection of `presence.lock` to coordinate autonomous agents.
- **Goal**: Spawn the first "Archivist" Ghost Session to monitor system pulse autonomously.

### Nag Ladder: Next Feature Slice (kingdonb/mecris#139)
- **Tier 2 message content**: Currently uses `use_template: False` with `fallback_message`. Refine the coaching copy for escalated walk/Beeminder alerts.
- **WhatsApp Template approval**: Decide if a high-urgency template is needed to bypass the 24h window for Tier 3 alerts.

### PR-Test Fix (kingdonb/mecris#163)
- Deployment of `pr-test.yml` fix is blocked on `workflow` scope for `MECRIS_BOT_CLASSIC_PAT`.
- Kingdon must update token scopes in GitHub Secrets before this can proceed.

## Infrastructure Notes
- **NO RECURSIVE GLOBAL GREP**: Root-level `grep -r` is blacklisted. Use targeted `include_pattern` or `dir_path`.
- **MASTER_ENCRYPTION_KEY**: Required in `.env` for all local PII decryption.
- **Nag Ladder tier semantics**: 
    - Tier 1: WhatsApp Template (Gentle)
    - Tier 2: WhatsApp Freeform (Escalated, 6h idle)
    - Tier 3: WhatsApp High Urgency (Critical, <2h runway)
- **Global Rate Limit**: 2 messages per hour across ALL channels.
