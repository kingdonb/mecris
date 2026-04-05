# Next Session: Token Rotation — cli/main.py refresh_token flow

## Current Status (2026-04-05)
- `services/auth_service.py` now performs **real RSA signature verification** via `PyJWKClient` in cloud mode — commit `3e41841`.
- Standalone mode (`MECRIS_MODE=standalone`) retains relaxed decode (expiry-only check) for local dev.
- Issuer claim is now enforced after signature verification (was silently ignored with `pass`).
- `tests/test_auth_service.py` added: 7 tests covering valid token, wrong-key 401, expiry 401, issuer mismatch 401, standalone passthrough, standalone expiry, and JWKS non-invocation in standalone.
- `message_log.error_msg` is encrypted at rest (AES-256-GCM) — committed in `4de2ebd`.

## Verified This Session
- [x] **JWKS signature verification**: `PyJWKClient` fetches keys from `{POCKET_ID_URL}/.well-known/jwks.json`; forged tokens (wrong RSA key) receive 401 — confirmed by `tests/test_auth_service.py` (7/7 pass).
- [x] **Issuer enforcement**: tokens with `iss != OIDC_ISSUER` raise 401 after signature is verified.
- [x] **Standalone mode unchanged**: no JWKS call, expiry-only check preserved.

## Pending Verification (Next Session)
- [ ] **Token Rotation**: `cli/main.py` saves `refresh_token` in `credentials.json` but does not attempt to use it on expiry — the user is re-prompted to open the browser. Implement `exchange_refresh_token()` in `services/auth_utils.py` and call it in the CLI login flow when the access token is expired.
- [ ] **CI verification**: Confirm `test_pii_encryption.py` (commit `4de2ebd`) and `test_auth_service.py` (commit `3e41841`) pass in the full CI venv (requires `mcp`, `playwright`, `psycopg2`). The psycopg2 test (`test_usage_sessions_notes_are_encrypted_at_rest`) fails in the stripped bot env — expected.
- [ ] **JWKS cache behavior**: `PyJWKClient` caches keys in-process. Verify that key rotation at the IdP side is handled (PyJWT's `PyJWKClient` supports cache TTL via `lifespan` param — consider whether to set it explicitly).

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces it.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key) — if unset, encryption silently skips and logs a warning.
- JWKS URI defaults to `{POCKET_ID_URL}/.well-known/jwks.json`; override via `OIDC_JWKS_URI` env var.
- Plan issue for this session: yebyen/mecris#95 (closed complete).
