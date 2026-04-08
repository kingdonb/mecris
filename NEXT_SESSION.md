# Next Session: kingdonb/mecris#175 Review + Live Verification Backlog

## Current Status (2026-04-08)
- **kingdonb/mecris#175 open**: PR from yebyen:main → kingdonb:main containing Ghost Archivist SYS-001 refactor + `/languages` has_goal/sort fix. Awaiting kingdonb review/merge.
- **Arabic reminders enhanced (yebyen/mecris#119 DONE)**: All `_handle_arabic_pressure` message variants now include Arabic-script phrases; Tier 2 escalation fallback also contains Arabic. 51 total tests pass (6 coaching, 45 reminder). Commit `76522a4`.
- **Encryption regression tests fixed (yebyen/mecris#118 DONE)**: 270 tests pass, 0 fail. Commit `dd659ef`.
- **Ghost Archivist continuous reconciliation DONE**: `should_ghost_wake_up` uses idempotency-only (12h cooldown) per SYS-001.
- **`/languages` endpoint fixed**: `has_goal` derived from `beeminder_slug`, Beeminder-tracked languages sorted first.
- **`/aggregate-status` tests added (yebyen/mecris#120 DONE)**: 3 new tests for `get_daily_aggregate_status` schema, `all_clear=True`, and `all_clear=False`. 275 total tests pass. Commit `b0db38c`.

## Verified This Session
- [x] **`get_daily_aggregate_status` test coverage**: 3 tests assert schema keys (`goals`, `satisfied_count`, `total_count`, `all_clear`, `score`, `components`), `all_clear=True` when all goals satisfied, `all_clear=False` when walk missing. All pass. Commit `b0db38c`.
- [x] **Plan issue yebyen/mecris#120**: Created and closed with evidence.

## Pending Verification (Next Session)
- [ ] **kingdonb/mecris#175 review**: Check if kingdonb has reviewed/merged the PR. If merged, upstream sync is complete.
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
