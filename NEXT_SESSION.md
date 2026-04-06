# Next Session: kingdonb needs to integrate yebyen fork fixes into kingdonb/mecris#173

## Current Status (2026-04-06)
- **yebyen/mecris#101 pr-test green at head `823b1e0`**: Merge conflict in NEXT_SESSION.md resolved; pr-test run 24048682519 passed. All 3 blockers resolved. Awaits kingdonb's merge approval.
- **kingdonb/mecris#173 still blocked**: Head is `4d16c9a9` — the 3 blockers (merge conflicts, cron, NEXT_SESSION.md) are still present in kingdonb's branch. CHANGES_REQUESTED review remains accurate.
- **Status comment posted on #173**: Explains that fixes are in yebyen's fork but NOT in kingdonb's branch. Directs kingdonb to pull yebyen/mecris#101's fixes into kingdonb:gemini-flash-rust-brain.
- **yebyen/mecris is in sync with kingdonb/mecris main** — both at `e642551`.

## Verified This Session (2026-04-06)
- [x] **NEXT_SESSION.md merge conflict resolved on gemini-flash-rust-brain**: Merged yebyen:main into PR branch, kept main's authoritative state, pushed `823b1e0`.
- [x] **pr-test green at `823b1e0`**: Run 24048682519 — success. Previous run 24048507350 had failed due to merge conflict.
- [x] **kingdonb/mecris#173 head still at `4d16c9a9`**: No new commits from kingdonb — CHANGES_REQUESTED review still accurate.
- [x] **Status comment posted on yebyen/mecris#101**: https://github.com/yebyen/mecris/pull/101#issuecomment-4194702789 — notes conflict fixed, pr-test green, ready to merge.

## Pending Verification (Next Session)
- [ ] **Merge yebyen/mecris#101**: pr-test green at `823b1e0`, blockers clear. Needs kingdonb's merge approval.
- [ ] **kingdonb/mecris#173 unblocked**: Needs kingdonb to pull yebyen's fixes (`823b1e0`) into kingdonb:gemini-flash-rust-brain. Once done, bot can re-review or kingdonb can self-merge.
- [ ] **CI verification of `test_auth_service.py`** (7 tests): Requires `fastapi`, `mcp`, `psycopg2` — should pass in CI (GitHub Actions full venv), not verifiable in bot env.
- [ ] **kingdonb/mecris#162 close**: Needs manual close by kingdonb.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` on both `main` and `gemini-flash-rust-brain` (yebyen fork) — do not re-enable. kingdonb's branch still has it enabled — that's one of the 3 blockers.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key) — if unset, encryption silently skips and logs a warning.
- JWKS URI defaults to `{POCKET_ID_URL}/.well-known/jwks.json`; override via `OIDC_JWKS_URI` env var.
- `ghost.archivist.run` is `async def` — always `await` it in tests; use `asyncio.run()` in sync entry points.
- **Classic PAT scope**: GITHUB_CLASSIC_PAT (repo scope, as yebyen) can post comments and reviews on kingdonb/mecris. MCP tool cannot (fine-grained token is yebyen/mecris only). Use `GITHUB_TOKEN="$GITHUB_CLASSIC_PAT" gh api` pattern for kingdonb/mecris writes.
- **Fork divergence**: yebyen:gemini-flash-rust-brain (`823b1e0`) is AHEAD of kingdonb:gemini-flash-rust-brain (`4d16c9a9`). The two PRs (#101 and #173) share a branch name but are in separate forks with different histories.
