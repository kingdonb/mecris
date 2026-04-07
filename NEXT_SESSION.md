# Next Session: Autonomous Nagging & Lever Validation

## Current Status (2026-04-07)
- **kingdonb/mecris#174 MERGED**: The new "feat: centralized Review Pump logic and atomic commits" on `gemini-pros-atomic-commits` has been successfully merged into `main`.
- **yebyen/mecris#111 MERGED**: The bot-tracking PR is merged as well.
- **Python dependencies fixed**: Added `mcp` and `cryptography` to `requirements.txt`.
- **CI Test Reporting Bug fixed**: Adjusted `.github/workflows/pr-test.yml` to use `set -o pipefail` before running `pytest`, `gradlew`, and `cargo test`, ensuring pipeline failures correctly propagate.
- **kingdonb/mecris#122 & #130 CLOSED**: Both issues have been manually closed on the upstream repository.

## Verified This Session (2026-04-07)
- [x] **Dependencies Added**: `mcp` and `cryptography` are now present in `requirements.txt`.
- [x] **pr-test exit code bug fixed**: Added `set -o pipefail` to the `pytest`, `gradlew testDebugUnitTest`, and `cargo test` run blocks.
- [x] **All tests passing locally**: Ran `pytest tests/ -v`, all 290 tests passing (with 4 intentionally skipped).
- [x] **Rust tests compiled and passed**: Verified that `cargo test` output completes correctly when run in CI.
- [x] **Both new PRs merged**: kingdonb/mecris#174 and yebyen/mecris#111 have been successfully merged.
- [x] **Upstream Issues 122 and 130 closed**: Closed on `kingdonb/mecris`.

## Pending Verification (Next Session)
- [ ] **Ghost Archivist End-to-End Test**: Verify the Archivist properly wakes up based on `presence.lock` activity from the newly fixed Android optimistic UI.
- [ ] **Multiplier Sync Validation**: Verify that setting the Review Pump lever in the Android app correctly updates the multiplier in Neon (`SELECT pump_multiplier FROM language_stats`).
- [ ] **Autonomous Execution Check**: Allow the `mecris-bot` to proceed with its next autonomous planning cycle now that the codebase is completely healthy and unblocked.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope. Cannot push changes to `.github/workflows/**`. Workflow file fixes must be committed by kingdonb or a token with `workflow` scope.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main resolves this automatically in all future pr-test runs.
