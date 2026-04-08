# Next Session: kingdonb/mecris#176 Review + Live Verification Backlog

## Current Status (2026-04-08)
- **kingdonb/mecris#176 open**: PR from yebyen:main → kingdonb:main containing 13 commits of test improvements (encryption regression, Arabic-script coverage, aggregate-status tests, vacation_mode branch coverage). Awaiting kingdonb review/merge.
- **Histories diverged by 1 commit**: kingdonb:main has `0e178dc` (fix sync-service: remove unused JwtClaims struct in Rust) that yebyen:main does not. No Python conflict expected — divergent file is `mecris-go-spin/sync-service/src/lib.rs`.
- **kingdonb/mecris#175 was closed without merging** (head=base=`0e178dc` at close time, not via GitHub merge). All test commits from this week are now in #176 instead.
- **275+ Python tests pass** on yebyen:main (verified across all PRs #118–#121).

## Verified This Session
- [x] **kingdonb/mecris#175 status**: Confirmed closed NOT merged. Commits not in kingdonb:main.
- [x] **kingdonb/mecris#176 opened**: PR created with head `530e834` (yebyen:main), base `0e178dc` (kingdonb:main). 13 commits ahead, 1 behind. No Python conflicts.
- [x] **Divergent commit identified**: `0e178dc` only touches `mecris-go-spin/sync-service/src/lib.rs` (Rust) — safe to merge via PR.

## Pending Verification (Next Session)
- [ ] **kingdonb/mecris#176 review**: Check if kingdonb has reviewed/merged the PR. If merged, upstream sync is complete.
- [ ] **yebyen:main sync from upstream**: After #176 is merged, yebyen:main needs to pull the Rust fix (`0e178dc`) from kingdonb to stay in sync. Until then, yebyen:main is 1 commit behind kingdonb:main.
- [ ] **Multiplier Sync Validation**: Verify that setting the Review Pump lever in the Android app correctly updates the multiplier in Neon (`SELECT pump_multiplier FROM language_stats`). Requires live device + Neon access.
- [ ] **Ghost Archivist End-to-End**: Run the scheduler locally, let the archivist job fire, and confirm via logs that it correctly reconciles state without pushing fake data to Beeminder. The code is correct; the live verification is still needed.
- [ ] **kingdonb/mecris#132 verification**: The failover sync Rust implementation needs live verification — trigger `/internal/failover-sync` and confirm `daily_completions` is non-zero in Neon if reviews were done.
- [ ] **kingdonb/mecris#127 manual close**: Bot cannot comment on/close kingdonb/mecris issues (PAT scoped to yebyen only). kingdonb should close #127 as superseded by #132.
- [ ] **Android app has_goal UI**: Confirm the Android app picks up the new `has_goal=false` flag and visually dims untracked languages. Requires live app test.
- [ ] **Majesty Cake Android integration**: `/aggregate-status` backend is complete and tested; Android app needs to consume it for the unified goal progress widget (kingdonb/mecris#170).

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope. Workflow file fixes must be committed by kingdonb or a token with `workflow` scope.
- **Fine-grained PAT**: `GITHUB_TOKEN` is scoped to yebyen/mecris only — cannot comment or close issues on kingdonb/mecris. Use `GITHUB_CLASSIC_PAT` via `gh` CLI to create PRs on kingdonb/mecris.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main resolves this automatically.
- **psycopg2 not installed in CI runner**: `test_presence_neon.py` has pre-existing failures due to missing DB driver — not a regression.
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, {"NEON_DB_URL": ..., "DEFAULT_USER_ID": ...})` + `patch("psycopg2.connect")` before importing. See `_make_mcp_importable()` in `test_mcp_server.py`, `test_coaching.py`, `test_encryption_regression.py`.
- **test_standalone_access.py / test_unauthorized_access.py** require a real NEON_DB_URL — skip with `--ignore` in CI; they fail at collection time when `NEON_DB_URL` points to an unreachable host.
