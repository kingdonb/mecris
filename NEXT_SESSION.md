# Next Session: Review kingdonb/mecris#177 + Live Verification Backlog

## Current Status (2026-04-08)
- **kingdonb/mecris#177 open**: PR from yebyen:main → kingdonb:main with 6 commits — CI fixes, encrypted credential tests, SQL migration 003. Awaiting kingdonb review + CI.
- **Repos diverged (yebyen ahead by 6)**: Once #177 merges, repos will re-sync. No action needed until then.
- **Full test suite clean**: 282 passed, 5 skipped, 0 errors — confirmed this session.
- **PII encryption live** (d1d32b5): beeminder_user_encrypted column active in Neon; BeeminderClient decrypts at runtime.
- **Async sync live** (66396ee): Spin returns 202 Accepted; scraper parallelized.
- **Multi-tenancy SQL migration** (5f5141f): `scripts/migrations/003_multi_tenancy.sql` committed — idempotent migration for `language_stats` and `budget_tracking` `user_id` columns.

## Verified This Session
- [x] **kingdonb/mecris#177 opened**: PR exists, head SHA `a2b9003`, base SHA `01a6cdc`, state open.
- [x] **yebyen/mecris#126 closed**: Plan issue closed with completion comment.

## Pending Verification (Next Session)
- [ ] **kingdonb/mecris#177 CI**: Confirm CI passes on the upstream PR. If it fails, diagnose and fix in yebyen:main then force-push... actually: fix in a new commit and update the PR.
- [ ] **Multiplier Sync Validation**: Verify that setting the Review Pump lever in the Android app correctly updates the multiplier in Neon (`SELECT pump_multiplier FROM language_stats`). Requires live device + Neon access.
- [ ] **Ghost Archivist End-to-End**: Run the scheduler locally, let the archivist job fire, and confirm via logs that it correctly reconciles state without pushing fake data to Beeminder. The code is correct; the live verification is still needed.
- [ ] **kingdonb/mecris#132 verification**: The failover sync Rust implementation needs live verification — trigger `/internal/failover-sync` and confirm `daily_completions` is non-zero in Neon if reviews were done.
- [ ] **kingdonb/mecris#127 manual close**: Bot cannot comment on/close kingdonb/mecris issues (PAT scoped to yebyen only). kingdonb should close #127 as superseded by #132.
- [ ] **Android app has_goal UI**: Confirm the Android app picks up the new `has_goal=false` flag and visually dims untracked languages. Requires live app test.
- [ ] **Majesty Cake Android integration**: `/aggregate-status` backend is complete and tested; Android app needs to consume it for the unified goal progress widget (kingdonb/mecris#170).
- [ ] **003_multi_tenancy.sql live run**: The migration script needs to be run against live Neon to complete the schema change (`psql $NEON_DB_URL -f scripts/migrations/003_multi_tenancy.sql`). Code-level scoping is already in place; the DDL migration just makes it canonical.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope. Workflow file fixes must be committed by kingdonb or a token with `workflow` scope.
- **Fine-grained PAT**: `GITHUB_TOKEN` is scoped to yebyen/mecris only — cannot comment or close issues on kingdonb/mecris. Use `GITHUB_CLASSIC_PAT` via `gh` CLI to create PRs on kingdonb/mecris.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main resolves this automatically.
- **psycopg2 not installed in CI runner**: `test_presence_neon.py` has pre-existing failures due to missing DB driver — not a regression.
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, {"NEON_DB_URL": ..., "DEFAULT_USER_ID": ...})` + `patch("psycopg2.connect")` before importing. See `_make_mcp_importable()` in `test_mcp_server.py`, `test_coaching.py`, `test_encryption_regression.py`.
- **test_standalone_access.py / test_unauthorized_access.py**: Now skipped at collection time when `NEON_DB_URL` is absent via `pytest_ignore_collect` in `tests/conftest.py`. They require a live Neon DB and cannot be mocked without restructuring.
- **BeeminderClient note**: `UsageTracker.__init__` requires `NEON_DB_URL` even in the no-DB fallback path of `_load_credentials()` — mock UsageTracker when testing the env-var-only path.
- **playwright is installed**: It's in requirements.txt and installs via pip. The prior session's note about playwright CI gap was actually the NEON_DB_URL collection error — now fixed.
- **Multi-tenancy schema**: `language_stats` PK is `(user_id, language_name)`; `budget_tracking` has `user_id UNIQUE`. All queries in Python services scope by user_id. SQL migration 003 formalizes this for live Neon.
