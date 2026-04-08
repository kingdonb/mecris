# Next Session: Live Verification Backlog + Android Integration

## Current Status (2026-04-08)
- **kingdonb/mecris#176 merged**: All test improvements from yebyen:main are now in kingdonb:main. Both repos at `01a6cdc`.
- **Repos in sync**: yebyen:main == kingdonb:main (no divergence).
- **BeeminderClient._load_credentials() unit tests added** (5b91d56): 4 tests covering encrypted path, plaintext fallback, env-var fallback, no-NEON_DB_URL path — all pass.
- **Total Python tests passing**: 4 new in test_beeminder_credentials.py; rest of suite stable except playwright-dependent tests (pre-existing CI gap).
- **PII encryption live** (d1d32b5): beeminder_user_encrypted column active in Neon; BeeminderClient decrypts at runtime.
- **Async sync live** (66396ee): Spin returns 202 Accepted; scraper parallelized.

## Verified This Session
- [x] **kingdonb/mecris#176 merged**: Confirmed closed with merged_at timestamp at 2026-04-08T15:29:25Z.
- [x] **yebyen:main sync**: Both repos at `01a6cdc` — fully in sync.
- [x] **BeeminderClient._load_credentials() tested**: 4 unit tests written and passing (yebyen/mecris#123).

## Pending Verification (Next Session)
- [ ] **Multiplier Sync Validation**: Verify that setting the Review Pump lever in the Android app correctly updates the multiplier in Neon (`SELECT pump_multiplier FROM language_stats`). Requires live device + Neon access.
- [ ] **Ghost Archivist End-to-End**: Run the scheduler locally, let the archivist job fire, and confirm via logs that it correctly reconciles state without pushing fake data to Beeminder. The code is correct; the live verification is still needed.
- [ ] **kingdonb/mecris#132 verification**: The failover sync Rust implementation needs live verification — trigger `/internal/failover-sync` and confirm `daily_completions` is non-zero in Neon if reviews were done.
- [ ] **kingdonb/mecris#127 manual close**: Bot cannot comment on/close kingdonb/mecris issues (PAT scoped to yebyen only). kingdonb should close #127 as superseded by #132.
- [ ] **Android app has_goal UI**: Confirm the Android app picks up the new `has_goal=false` flag and visually dims untracked languages. Requires live app test.
- [ ] **Majesty Cake Android integration**: `/aggregate-status` backend is complete and tested; Android app needs to consume it for the unified goal progress widget (kingdonb/mecris#170).
- [ ] **playwright gap in CI**: Several tests fail with `ModuleNotFoundError: No module named 'playwright'` in this environment. Not a regression — pre-existing. Consider adding `playwright` to test requirements or skipping affected tests in CI.

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
- **BeeminderClient note**: `UsageTracker.__init__` requires `NEON_DB_URL` even in the no-DB fallback path of `_load_credentials()` — mock UsageTracker when testing the env-var-only path.
