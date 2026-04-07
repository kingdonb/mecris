# Next Session: kingdonb needs to integrate yebyen fork fixes into kingdonb/mecris#173

## Current Status (2026-04-07)
- **yebyen/mecris#101 pr-test green at head `351293c`**: Run 24057135798 passed. NEXT_SESSION.md synced from main into feature branch (was stale from prior session); all Python + Android tests pass. Awaits kingdonb's merge approval.
- **kingdonb/mecris#173 still blocked**: Head is `4d16c9a9` — the 3 blockers (merge conflicts, cron, NEXT_SESSION.md) are still present in kingdonb's branch. CHANGES_REQUESTED review remains accurate.
- **Status comment posted on #101**: https://github.com/yebyen/mecris/pull/101#issuecomment-4195649864 — notes pr-test green at 351293c, NEXT_SESSION.md conflict resolved.
- **yebyen/mecris main is 5 commits AHEAD of kingdonb/mecris main** — bot archive commits not yet in upstream.

## Verified This Session (2026-04-07)
- [x] **NEXT_SESSION.md conflict re-emerged**: 2 archive commits on main (`b9d111b`, `3d828a2`) created a fresh merge conflict in gemini-flash-rust-brain. Fixed via GitHub API commit `351293c`.
- [x] **pr-test run 24057135798 GREEN**: All tests pass at head `351293c` (gemini-flash-rust-brain).
- [x] **Status comment on yebyen/mecris#101**: Confirms pr-test green, explains NEXT_SESSION.md sync fix.
- [x] **Plan yebyen/mecris#110 closed**: Complete — validation criteria met.

## Pending Verification (Next Session)
- [ ] **Merge yebyen/mecris#101**: pr-test green at `351293c`, blockers clear. Needs kingdonb's merge approval.
- [ ] **kingdonb/mecris#173 unblocked**: Needs kingdonb to pull yebyen's fixes (`351293c`) into kingdonb:gemini-flash-rust-brain. Once done, bot can re-review or kingdonb can self-merge.
- [ ] **kingdonb/mecris#122 close**: Audited complete — needs kingdonb to close.
- [ ] **kingdonb/mecris#130 close**: Implemented and landed — needs kingdonb to close.
- [ ] **NEXT_SESSION.md drift is a recurring problem**: Every archive commit on main regenerates a merge conflict in gemini-flash-rust-brain. Consider adding NEXT_SESSION.md to `.gitattributes` with `merge=ours` strategy on the feature branch, or have pr-test workflow auto-resolve this file.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` on both `main` and `gemini-flash-rust-brain` (yebyen fork) — do not re-enable. kingdonb's branch still has it enabled — that's one of the 3 blockers.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key) — if unset, encryption silently skips and logs a warning.
- JWKS URI defaults to `{POCKET_ID_URL}/.well-known/jwks.json`; override via `OIDC_JWKS_URI` env var.
- `ghost.archivist.run` is `async def` — always `await` it in tests; use `asyncio.run()` in sync entry points.
- **Classic PAT scope**: GITHUB_CLASSIC_PAT (repo scope, as yebyen) can post comments and reviews on kingdonb/mecris. MCP tool cannot (fine-grained token is yebyen/mecris only). Use `GITHUB_TOKEN="$GITHUB_CLASSIC_PAT" gh api` pattern for kingdonb/mecris writes.
- **Fork divergence**: yebyen:gemini-flash-rust-brain (`351293c`) is AHEAD of kingdonb:gemini-flash-rust-brain (`4d16c9a9`). The two PRs (#101 and #173) share a branch name but are in separate forks with different histories.
