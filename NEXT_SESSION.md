# Next Session: kingdonb needs to integrate yebyen fork fixes into kingdonb/mecris#173

## Current Status (2026-04-06)
- **yebyen/mecris#101 still open**: pr-test green at head `7501805`, all 3 blockers resolved in yebyen's fork. Awaits kingdonb's merge approval.
- **kingdonb/mecris#173 still blocked**: Head is `4d16c9a9` — the 3 blockers (merge conflicts, cron, NEXT_SESSION.md) are still present in kingdonb's branch. My CHANGES_REQUESTED review is still accurate.
- **Status comment posted on #173**: Explains that fixes are in yebyen's fork but NOT in kingdonb's branch. Directs kingdonb to pull yebyen/mecris#101's fixes into kingdonb:gemini-flash-rust-brain.
- **yebyen/mecris is in sync with kingdonb/mecris main** — both at `ae8e1ba`.

## Verified This Session (2026-04-06)
- [x] **kingdonb/mecris#173 head still at `4d16c9a9`**: Confirmed — CHANGES_REQUESTED review remains accurate, no new commits on kingdonb's branch.
- [x] **Status comment posted on kingdonb/mecris#173**: https://github.com/kingdonb/mecris/pull/173#issuecomment-4194069091 — explains divergence between forks and path to resolution.
- [x] **yebyen/mecris#101 head unchanged at `7501805`**: pr-test run 24039612500 still valid.

## Pending Verification (Next Session)
- [ ] **Merge yebyen/mecris#101**: pr-test green, blockers clear in yebyen fork. Needs kingdonb's merge approval.
- [ ] **kingdonb/mecris#173 unblocked**: Needs kingdonb to pull yebyen's fixes (head `7501805`) into kingdonb:gemini-flash-rust-brain. Once done, bot can re-review or kingdonb can self-merge.
- [ ] **CI verification of `test_auth_service.py`** (7 tests): Requires `fastapi`, `mcp`, `psycopg2` — should pass in CI (GitHub Actions full venv), not verifiable in bot env.
- [ ] **kingdonb/mecris#162 close**: Needs manual close by kingdonb.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` on both `main` and `gemini-flash-rust-brain` (yebyen fork) — do not re-enable. kingdonb's branch still has it enabled — that's one of the 3 blockers.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key) — if unset, encryption silently skips and logs a warning.
- JWKS URI defaults to `{POCKET_ID_URL}/.well-known/jwks.json`; override via `OIDC_JWKS_URI` env var.
- `ghost.archivist.run` is `async def` — always `await` it in tests; use `asyncio.run()` in sync entry points.
- **Classic PAT scope**: GITHUB_CLASSIC_PAT (repo scope, as yebyen) can post comments and reviews on kingdonb/mecris. MCP tool cannot (fine-grained token is yebyen/mecris only). Use `GITHUB_TOKEN="$GITHUB_CLASSIC_PAT" gh api` pattern for kingdonb/mecris writes.
- **Fork divergence**: yebyen:gemini-flash-rust-brain (`7501805`) is AHEAD of kingdonb:gemini-flash-rust-brain (`4d16c9a9`) by 3 fix commits. The two PRs (#101 and #173) share a branch name but are in separate forks with different histories.
