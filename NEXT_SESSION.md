# Next Session: kingdonb needs to integrate yebyen fork fixes into kingdonb/mecris#173

## Current Status (2026-04-06)
- **yebyen/mecris#101 pr-test green at head `823b1e0`**: Merge conflict in NEXT_SESSION.md resolved; pr-test run 24048682519 passed. All 3 blockers resolved. Awaits kingdonb's merge approval.
- **kingdonb/mecris#173 still blocked**: Head is `4d16c9a9` — the 3 blockers (merge conflicts, cron, NEXT_SESSION.md) are still present in kingdonb's branch. CHANGES_REQUESTED review remains accurate.
- **Status comment posted on #173**: Explains that fixes are in yebyen's fork but NOT in kingdonb's branch. Directs kingdonb to pull yebyen/mecris#101's fixes into kingdonb:gemini-flash-rust-brain.
- **yebyen/mecris main is 5 commits AHEAD of kingdonb/mecris main** — bot archive commits not yet in upstream.

## Verified This Session (2026-04-06, triage session)
- [x] **kingdonb/mecris#162 CLOSED**: Confirmed closed by kingdonb on 2026-04-05 (state_reason: completed). Removed from pending list.
- [x] **kingdonb/mecris#122 audited complete**: Prior bot session (session 30, 2026-04-04) confirmed `surgicalUpdateInProgress` fully resolves the race condition. Awaits kingdonb to close.
- [x] **kingdonb/mecris#130 implemented**: Bot session 22 landed score-delta tracking in main via PR #165 (2026-04-04). Awaits kingdonb to close.
- [x] **Status comment posted on yebyen/mecris#101**: https://github.com/yebyen/mecris/pull/101#issuecomment-4195234759 — notes another session passed, still waiting for kingdonb.

## Pending Verification (Next Session)
- [ ] **Merge yebyen/mecris#101**: pr-test green at `823b1e0`, blockers clear. Needs kingdonb's merge approval.
- [ ] **kingdonb/mecris#173 unblocked**: Needs kingdonb to pull yebyen's fixes (`823b1e0`) into kingdonb:gemini-flash-rust-brain. Once done, bot can re-review or kingdonb can self-merge.
- [ ] **kingdonb/mecris#122 close**: Audited complete — needs kingdonb to close.
- [ ] **kingdonb/mecris#130 close**: Implemented and landed — needs kingdonb to close.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` on both `main` and `gemini-flash-rust-brain` (yebyen fork) — do not re-enable. kingdonb's branch still has it enabled — that's one of the 3 blockers.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key) — if unset, encryption silently skips and logs a warning.
- JWKS URI defaults to `{POCKET_ID_URL}/.well-known/jwks.json`; override via `OIDC_JWKS_URI` env var.
- `ghost.archivist.run` is `async def` — always `await` it in tests; use `asyncio.run()` in sync entry points.
- **Classic PAT scope**: GITHUB_CLASSIC_PAT (repo scope, as yebyen) can post comments and reviews on kingdonb/mecris. MCP tool cannot (fine-grained token is yebyen/mecris only). Use `GITHUB_TOKEN="$GITHUB_CLASSIC_PAT" gh api` pattern for kingdonb/mecris writes.
- **Fork divergence**: yebyen:gemini-flash-rust-brain (`823b1e0`) is AHEAD of kingdonb:gemini-flash-rust-brain (`4d16c9a9`). The two PRs (#101 and #173) share a branch name but are in separate forks with different histories.
