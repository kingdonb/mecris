# Next Session: PII Encryption & OIDC Hardening

## 🎯 Primary Goal: Database PII Encryption
- [ ] **Audit high-risk tables**: `message_log` (SMS content), `walk_inferences` (GPS/telemetry), `usage_sessions` (LLM notes).
- [ ] **Implement Field-Level Encryption**: Use the existing `EncryptionService` (AES-256-GCM) to migrate these columns from plaintext to encrypted storage.
- [ ] **TDG Verification**: Write tests to ensure that unauthenticated database access (e.g. via direct SQL) yields only ciphertext, while the application layer transparently decrypts for the authorized user.

## 🔒 Auth Hardening (The "Last Mile")
- [ ] **JWKS Integration**: Replace the "relaxed" signature check with real public key validation against the OIDC discovery endpoint.
- [ ] **Token Rotation**: Ensure the CLI can use `refresh_token` to maintain a session without re-opening the browser.

## ✅ Recently Completed
- [x] **Enforced JWT Authorization** on all FastAPI endpoints in `mcp_server.py`.
- [x] **Implemented Standalone vs Cloud Mode**: `MECRIS_MODE` toggle for local convenience vs cloud security.
- [x] **Familiar ID Resolution**: Login flow now resolves UUIDs to human-friendly usernames via Neon.
- [x] **Graceful CLI Interrupts**: Fixed the "double Ctrl-C" hang in the login loop.
