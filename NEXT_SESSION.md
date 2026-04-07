# Next Session: kingdonb/mecris#174 needs Python deps fixed (mcp, cryptography) before merge

## Current Status (2026-04-07)
- **yebyen/mecris#101 CLOSED** (not merged): kingdonb closed both old DMZ PRs (#101 and #173) without merging. The `gemini-flash-rust-brain` branch is superseded.
- **kingdonb/mecris#174 OPEN**: New PR "feat: centralized Review Pump logic and atomic commits" on `gemini-pros-atomic-commits`. pr-test run 24080705977 completed — Android ✅, Python ⚠️ (icon shows ✅ but output has 11 collection errors: `mcp` and `cryptography` not in requirements.txt).
- **yebyen/mecris#111 OPEN**: Bot-tracking PR for the same `gemini-pros-atomic-commits` branch.
- **NEXT_SESSION.md conflict FIXED**: `.gitattributes` with `merge=union` deployed to main at `76f2e89`. Prevents the recurring pr-test merge conflict blocker permanently.
- **yebyen/mecris main is 11+ commits AHEAD of kingdonb/mecris main** — bot archive commits not yet in upstream.

## Verified This Session (2026-04-07)
- [x] **Both old PRs superseded**: kingdonb/mecris#173 and yebyen/mecris#101 closed (not merged) at ~2026-04-07T02:56Z
- [x] **New PR exists**: kingdonb/mecris#174 + yebyen/mecris#111 on `gemini-pros-atomic-commits`
- [x] **pr-test run 24080705977 GREEN (workflow level)**: All steps succeeded, comment posted at https://github.com/kingdonb/mecris/pull/174#issuecomment-4198872455
- [x] **Android tests PASS**: BUILD SUCCESSFUL, 24 tasks
- [x] **Python import errors confirmed**: `mcp` and `cryptography` missing from `requirements.txt` — exit code bug in pr-test masks this as ✅ when real status is ❌
- [x] **NEXT_SESSION.md fix deployed**: `.gitattributes merge=union` at commit `76f2e89` — no more per-session merge conflict resolution needed
- [x] **Plan yebyen/mecris#113 closed**: Complete — validation criteria met

## Pending Verification (Next Session)
- [ ] **kingdonb/mecris#174 needs Python deps**: `mcp` and `cryptography` must be added to `requirements.txt` before Python tests can pass. Bot posted clarification comment at https://github.com/kingdonb/mecris/pull/174#issuecomment-4198882038
- [ ] **pr-test exit code bug**: The `tee` pipe masks pytest's real exit code (line 97-99 of pr-test.yml). Python failures appear as ✅. This needs `pipefail` or `PIPESTATUS` fix — but workflow file changes require `workflow` scope which bot tokens lack. Must be fixed by kingdonb.
- [ ] **Rust tests not yet run**: pr-test.yml on yebyen/main doesn't include Rust tests. The PR adds them, but they'll only run after the PR is merged and the workflow is updated.
- [ ] **kingdonb/mecris#122 close**: Audited complete — still needs kingdonb to close.
- [ ] **kingdonb/mecris#130 close**: Implemented and landed — still needs kingdonb to close.
- [ ] **yebyen/mecris#111**: Review/close once kingdonb/mecris#174 is handled.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope. Cannot push changes to `.github/workflows/**`. Workflow file fixes must be committed by kingdonb or a token with `workflow` scope.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main resolves this automatically in all future pr-test runs.
- **pr-test pipe exit code bug**: Line 97: `.venv/bin/pytest ... | tee ... && echo "exit_code=$?"` — `$?` captures `tee`'s exit code (0), not pytest's. Needs `set -o pipefail` or `PIPESTATUS[0]` fix.
