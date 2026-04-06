# Next Session: Merge yebyen/mecris#101 (DMZ PR unblocked, pr-test green)

## Current Status (2026-04-06)
- **DMZ PR blockers resolved**: mecris-bot fixed all 3 CHANGES_REQUESTED items on `gemini-flash-rust-brain` (session 4, yebyen/mecris#105): merge conflicts in `src/lib.rs`, cron removed from `spin.toml`, NEXT_SESSION.md aligned with main.
- **pr-test PASSED**: run https://github.com/yebyen/mecris/actions/runs/24039612500 — head `7501805`, all jobs green.
- **yebyen/mecris#101 ready for merge review**: PR comment posted noting unblocked status.
- **kingdonb/mecris#173 still needs attention**: Same branch (`gemini-flash-rust-brain`) — the fixes apply equally, but #173 was reviewed CHANGES_REQUESTED and needs a follow-up review/approval from the upstream maintainer.
- **yebyen/mecris is in sync with kingdonb/mecris main** — both at `ae8e1ba`.

## Verified This Session (2026-04-06)
- [x] **Merge conflicts resolved in `mecris-go-spin/sync-service/src/lib.rs`**: Both conflict regions removed; HEAD versions kept (authenticated routing, authenticated `handle_languages_get`). 59 lines of conflict markers and duplicate android-fix code removed.
- [x] **Cron disabled in `mecris-go-spin/sync-service/spin.toml`**: `[[trigger.cron]]` block removed. Matches main branch policy.
- [x] **NEXT_SESSION.md aligned with main**: Gemini's branch content replaced with main's pending items to allow clean git merge in pr-test.
- [x] **pr-test green on head `7501805`**: https://github.com/yebyen/mecris/actions/runs/24039612500 — success.
- [x] **PR #101 comment posted**: Blockers resolved, pr-test link, merge-ready status noted.

## Pending Verification (Next Session)
- [ ] **Merge yebyen/mecris#101**: pr-test green, blockers clear. Needs kingdonb's merge approval.
- [ ] **Review kingdonb/mecris#173**: Same branch as #101 — fixes are in. Consider re-reviewing #173 with approval or a comment confirming the blockers are addressed. Use GITHUB_CLASSIC_PAT for kingdonb/mecris writes.
- [ ] **CI verification of `test_auth_service.py`** (7 tests): Requires `fastapi`, `mcp`, `psycopg2` — should pass in CI (GitHub Actions full venv), not verifiable in bot env.
- [ ] **kingdonb/mecris#162 close**: Needs manual close by kingdonb.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` on both `main` and `gemini-flash-rust-brain` — do not re-enable. Gemini's PR tried to re-enable it; flagged as a blocker on BOTH PRs.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key) — if unset, encryption silently skips and logs a warning.
- JWKS URI defaults to `{POCKET_ID_URL}/.well-known/jwks.json`; override via `OIDC_JWKS_URI` env var.
- `ghost.archivist.run` is `async def` — always `await` it in tests; use `asyncio.run()` in sync entry points.
- **Jet-Propelled DMZ** (both PRs): Architecture is sound — Python Vanguard as spec, Rust Iron Core as jet, shadow execution + `jet_divergence` logging, `mecris-core/` UniFFI scaffolding for Android bindings.
- **Classic PAT scope**: GITHUB_CLASSIC_PAT (repo scope, as yebyen) can post reviews on kingdonb/mecris. MCP tool cannot (fine-grained token is yebyen/mecris only). Use `GITHUB_TOKEN="$GITHUB_CLASSIC_PAT" gh api` pattern for kingdonb/mecris writes.
