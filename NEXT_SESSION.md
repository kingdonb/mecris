# Next Session: Await Gemini's PR fixes on yebyen/mecris#101 (3 blockers)

## Current Status (2026-04-06)
- **yebyen/mecris#101 under CHANGES_REQUESTED review**: mecris-bot reviewed Gemini Flash's Jet-Propelled DMZ PR and found 3 blocking issues (see review comment on #101).
- Auth hardening stack fully merged upstream — kingdonb merged via `7315d67`.
- `PyJWKClient` has `lifespan=300` (commit `ab1f723`) — JWKS cache TTL bounded to 5 minutes.
- `try_token_refresh()` threshold raised from 60s → 1800s — CLI triggers proactive refresh at 30 min remaining.
- All archivist tests pass (14/14 after async/await fix).

## Verified This Session (2026-04-06)
- [x] **PR #101 Review**: Reviewed yebyen/mecris#101 (Gemini's Jet-Propelled DMZ architecture). Posted CHANGES_REQUESTED with 3 blockers documented. Did NOT merge. Did NOT run pr-test (compile-blocking conflict markers).

## Pending Verification (Next Session)
- [ ] **yebyen/mecris#101 blockers resolved?** Check if Gemini fixed: (1) unresolved merge conflicts in `sync-service/src/lib.rs`, (2) Spin Cron re-enabled in `spin.toml`, (3) NEXT_SESSION.md destructively overwritten. Once fixed, re-review and run `/mecris-pr-test 101`.
- [ ] **CI verification of `test_auth_service.py`** (7 tests): Requires `fastapi`, `mcp`, `psycopg2` — bot env lacks these. Should pass in CI (GitHub Actions full venv).
- [ ] **kingdonb/mecris#162 close**: Closing comment is posted. Kingdonb needs to close it manually.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` on `main` — do not re-enable. Gemini's PR tried to re-enable it; that was flagged as a blocker.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key) — if unset, encryption silently skips and logs a warning.
- JWKS URI defaults to `{POCKET_ID_URL}/.well-known/jwks.json`; override via `OIDC_JWKS_URI` env var.
- `PyJWKClient` `lifespan=300` bounds in-process JWKS cache TTL — keys refresh from OIDC endpoint every ~5 min.
- `ghost.archivist.run` is `async def` — always `await` it in tests; use `asyncio.run()` in sync entry points.
- **Jet-Propelled DMZ (yebyen/mecris#101)**: Architecture concept is sound (Python Vanguard as spec, Rust Iron Core as jet, shadow execution + `jet_divergence` logging). Value is there — just needs the 3 blockers resolved before merge.
