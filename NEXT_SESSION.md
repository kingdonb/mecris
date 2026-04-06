# Next Session: Await Gemini's blocker fixes on yebyen/mecris#101 + kingdonb/mecris#173

## Current Status (2026-04-06)
- **Both DMZ PRs under CHANGES_REQUESTED**: yebyen/mecris#101 (reviewed 2026-04-06 session 1) and kingdonb/mecris#173 (reviewed 2026-04-06 session 2) both have CHANGES_REQUESTED posted. Same head commit (`4d16c9a`), same 3 blockers.
- **No new Gemini commits since review**: Branch `gemini-flash-rust-brain` head is still `4d16c9a`. Gemini's progress comment on kingdonb#173 outlines next steps (UniFFI bindings, Python/Kotlin wrappers) but those commits have not been pushed.
- **yebyen/mecris is in sync with kingdonb/mecris main** — `ae8e1ba` on both.
- `CONTRIBUTING.md` (replacing constitution) and `mecris-core/` UniFFI scaffolding from the Gemini PR are noted as sound foundations — value is there, just blocked on 3 fixable issues.

## Verified This Session (2026-04-06)
- [x] **kingdonb/mecris#173 reviewed**: CHANGES_REQUESTED posted (review ID 4061831284) via classic PAT as yebyen. Identical 3 blockers to yebyen#101 documented with cross-reference.
- [x] **Upstream sync verified**: yebyen/mecris main is at same SHA as kingdonb/mecris main — no drift.
- [x] **No Gemini fixes pushed**: Confirmed yebyen#101 head still `4d16c9a` — blocker resolution has not started.

## Pending Verification (Next Session)
- [ ] **Both PR blockers resolved?** Check if Gemini pushed new commits to `gemini-flash-rust-brain` resolving: (1) merge conflict markers in `mecris-go-spin/sync-service/src/lib.rs`, (2) Spin Cron disabled in `spin.toml`, (3) NEXT_SESSION.md pending items preserved. Once resolved, re-review and run `/mecris-pr-test 101`.
- [ ] **CI verification of `test_auth_service.py`** (7 tests): Requires `fastapi`, `mcp`, `psycopg2` — bot env lacks these. Should pass in CI (GitHub Actions full venv).
- [ ] **kingdonb/mecris#162 close**: Closing comment is posted. Kingdonb needs to close it manually.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` on `main` — do not re-enable. Gemini's PR tried to re-enable it; that was flagged as a blocker on BOTH PRs.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key) — if unset, encryption silently skips and logs a warning.
- JWKS URI defaults to `{POCKET_ID_URL}/.well-known/jwks.json`; override via `OIDC_JWKS_URI` env var.
- `PyJWKClient` `lifespan=300` bounds in-process JWKS cache TTL — keys refresh from OIDC endpoint every ~5 min.
- `ghost.archivist.run` is `async def` — always `await` it in tests; use `asyncio.run()` in sync entry points.
- **Jet-Propelled DMZ** (both PRs): Architecture is sound — Python Vanguard as spec, Rust Iron Core as jet, shadow execution + `jet_divergence` logging, `mecris-core/` UniFFI scaffolding for Android bindings. Merge-blocked only on 3 procedural issues.
- **Classic PAT scope**: GITHUB_CLASSIC_PAT (repo scope, as yebyen) can post reviews on kingdonb/mecris. MCP tool cannot (fine-grained token is yebyen/mecris only). Use `GITHUB_TOKEN="$GITHUB_CLASSIC_PAT" gh api` pattern for kingdonb/mecris writes.
