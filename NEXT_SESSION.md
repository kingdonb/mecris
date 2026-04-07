# Next Session: Multiplier Sync Validation (Review Pump lever → Neon DB)

## Current Status (2026-04-07)
- **kingdonb/mecris#175 open**: PR from yebyen:main → kingdonb:main containing Ghost Archivist SYS-001 refactor + `/languages` has_goal/sort fix. Awaiting kingdonb review/merge.
- **Ghost Archivist continuous reconciliation DONE**: `should_ghost_wake_up` now uses idempotency-only (12h cooldown); night-window (2-5 AM UTC) and human-silence checks removed per SYS-001 spec.
- **kingdonb/mecris#121 resolved**: `/languages` endpoint now derives `has_goal` from `beeminder_slug` and sorts Beeminder-tracked languages before untracked ones. 2 new tests pass.
- **Encryption regression tests fixed (yebyen/mecris#118)**: `test_encryption_regression_message_log_content` and `_walk_gps_points` now use `_make_mcp_importable()` pattern and import inside env patch context. 270 tests pass, 0 fail.

## Verified This Session
- [x] **Encryption regression tests fixed**: All 4 tests in `test_encryption_regression.py` pass when run alone AND in the full suite. Commit `dd659ef`.
- [x] **Plan issue yebyen/mecris#118**: Created and closed with evidence.

## Pending Verification (Next Session)
- [ ] **kingdonb/mecris#175 review**: Check if kingdonb has reviewed/merged the PR. If merged, upstream sync is complete.
- [ ] **Multiplier Sync Validation**: Verify that setting the Review Pump lever in the Android app correctly updates the multiplier in Neon (`SELECT pump_multiplier FROM language_stats`). Requires live device + Neon access.
- [ ] **Ghost Archivist End-to-End**: Run the scheduler locally, let the archivist job fire, and confirm via logs that it correctly reconciles state without pushing fake data to Beeminder. The code is correct; the live verification is still needed.
- [ ] **kingdonb/mecris#132 verification**: The failover sync Rust implementation needs live verification — trigger `/internal/failover-sync` and confirm `daily_completions` is non-zero in Neon if reviews were done.
- [ ] **kingdonb/mecris#127 manual close**: Bot cannot comment on/close kingdonb/mecris issues (PAT scoped to yebyen only). kingdonb should close #127 as superseded by #132.
- [ ] **Android app has_goal UI**: Confirm the Android app picks up the new `has_goal=false` flag and visually dims untracked languages. Requires live app test.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope. Workflow file fixes must be committed by kingdonb or a token with `workflow` scope.
- **Fine-grained PAT**: `GITHUB_TOKEN` is scoped to yebyen/mecris only — cannot comment or close issues on kingdonb/mecris. Use `GITHUB_CLASSIC_PAT` via `gh` CLI to create PRs on kingdonb/mecris.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main resolves this automatically.
- **psycopg2 not installed in CI runner**: `test_presence_neon.py` has pre-existing failures due to missing DB driver — not a regression.
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, {"NEON_DB_URL": ..., "DEFAULT_USER_ID": ...})` + `patch("psycopg2.connect")` before importing. See `_make_mcp_importable()` in `test_mcp_server.py`, `test_coaching.py`, `test_encryption_regression.py`.
