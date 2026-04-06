# Next Session: CI verification of test_auth_service.py (needs full venv)

## Current Status (2026-04-05)
- Auth hardening stack fully merged upstream — kingdonb merged via `7315d67`.
- `PyJWKClient` has `lifespan=300` (commit `ab1f723`) — JWKS cache TTL bounded to 5 minutes.
- `try_token_refresh()` threshold raised from 60s → 1800s (commit `18b7bbc`) — CLI now triggers proactive refresh before the last 30 min of access token life.
- `docs/AUTH_CONFIGURATION.md` updated (commit `18b7bbc`) — §5 CLI token refresh behavior, §6 server-side JWKS verification, env var table, standalone vs cloud mode.
- **Ghost archivist `TestRun` tests fixed** (commit `9221937`) — 7 tests were calling `async run()` without `await`; all 39 bot-compatible tests now pass.

## Verified This Session (2026-04-05)
- [x] **Archivist Ghost Session**: Implemented `ghost/archivist_logic.py` and `ghost/archivist.py` with autonomous wake-up heuristic (silence + UTC night window) and archival sync (Clozemaster).
- [x] **Reality Enforcement (DEFECT-003)**: Removed the "savior" 0.0 ghost heartbeat logic from `perform_archival_sync`. The system now correctly allows derailment if no actual activity is found.
- [x] **Database PII Encryption**: Audited and implemented encryption for high-risk fields: `message_log.content`, `walk_inferences.gps_route_points`, and `autonomous_turns` (summary/outcome).
- [x] **Infrastructure Portability**: Fixed `.mcp.json` to use relative paths and `uv` from system PATH.
- [x] **Import Resilience**: Refactored `usage_tracker.py` to use lazy imports for `psycopg2`, allowing the MCP server to initialize in environments (like GitHub Actions runners) without Postgres system headers.
- [x] **Schema Alignment**: Harmonized Neon database schema between `UsageTracker.py`, `mcp_server.py`, and `schema.sql`.
- [x] **`try_token_refresh()` threshold bump**: `exp < now + 1800` committed as `18b7bbc`.
- [x] **`test_auth_utils.py`**: 6/6 passed in bot env (Python 3.12, no venv) ✅
- [x] **`test_auth_server.py`**: 1 passed, 1 skipped (network-bound test expected) ✅
- [x] **`test_archivist.py`**: 14/14 passed after fixing async/await mismatch and adding round-robin test ✅
- [x] **Closing comment posted on kingdonb/mecris#162**: all deliverables documented, test results recorded.
- [x] **Upstream PR for `18b7bbc` is moot**: already merged into kingdonb/mecris main via `1ffb4a2`.
- [x] **Encryption Audit**: Verified that `message_log.content` is actually being stored as ciphertext in Neon (session 34).
- [x] **Schema Migration**: Migrated `message_log` table in Neon to add missing `id`, `content`, and `channel` columns (session 34).
- [x] **Archivist Heuristics**: Implemented night window (2 AM - 5 AM UTC) and human silence (1 hour) heuristics in `ghost/archivist_logic.py` (session 34).
- [x] **Round-Robin Sync**: Enabled `ghost/archivist.py` to iterate all users when no specific `MECRIS_USER_ID` is provided (session 34).

## Pending Verification (Next Session)
- [ ] **CI verification of `test_auth_service.py`** (7 tests): Requires `fastapi`, `mcp`, `psycopg2` — bot env lacks these. Should pass in CI (GitHub Actions full venv).
- [ ] **kingdonb/mecris#162 close**: Closing comment is posted. Kingdonb needs to close it manually.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key) — if unset, encryption silently skips and logs a warning.
- JWKS URI defaults to `{POCKET_ID_URL}/.well-known/jwks.json`; override via `OIDC_JWKS_URI` env var.
- `PyJWKClient` `lifespan=300` bounds in-process JWKS cache TTL — keys refresh from OIDC endpoint every ~5 min.
- `ghost.archivist.run` is `async def` — always `await` it in tests; use `asyncio.run()` in sync entry points.
