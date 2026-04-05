# Next Session: Start Ghost Archivist Phase C — Background Job Integration

## Current Status (Saturday, April 4, 2026 — session 30)
- **CLI PKCE Login FLOW COMPLETE**: The `mecris login` command now performs a full OIDC PKCE handshake.
    - [x] Secure Verifier/Challenge generation.
    - [x] Local Loopback Server captures redirects.
    - [x] Token Exchange implemented.
    - [x] JWT Decoding extracts User ID.
    - [x] Persistence to `~/.mecris/credentials.json`.
- **Ghost Archivist Foundation DONE**:
    - [x] `presence` table updated for human/ghost separation.
    - [x] `should_ghost_wake_up` logic implemented (12h silence + night window).
    - [x] `archivists_round_robin` implemented and tested.
- **Security & Stability**:
    - [x] All MCP tools enforced with `resolve_target_user`.
    - [x] Neon schema bugs fixed (budget_tracking SERIAL).
    - [x] 263 tests passed (4 skipped).
- **Repos in sync**: Reconciled with `mecris-bot` fixes.

## Verified This Session
- [x] `mecris login` opens browser and receives code. ✅
- [x] `mecris internal presence` reports correctly to Neon. ✅
- [x] Ghost wake-up logic handles silence/window correctly. ✅
- [x] Language sync service coordination test passing in CI. ✅

## Pending Verification (Next Session)
- [ ] **Ghost Phase C**: Integrate `archivists_round_robin` into `scheduler.py`'s 4-hour cycle.
- [ ] **Live CLI Login**: Perform a real login against metnoom.urmanac.com and verify token storage.

## Infrastructure Notes
- **PKCE Client ID**: Uses `POCKET_ID_CLIENT_ID` from `.env`.
- **Loopback Port**: Server binds to port 0 (random) and tells the redirect URI.
- **Test Exclusions**: `tests/test_scheduler_election.py` (requires live Neon).
- **Skipped Tests**: `test_loopback_server_captures_code` (timing flaky) + SMS tests (disabled).
