# Next Session: Identify new bot-actionable work from kingdonb's async sync feature

## Current Status (2026-04-09)
- **yebyen/mecris is synced with kingdonb/mecris**: Merge commit `5503f07` brings in `fa5e601` (PR #177 squash merge). `git log HEAD..upstream/main` is empty.
- **kingdonb merged PR #177** (2026-04-09T17:22:11Z): 13 commits squashed — CI fixes, encrypted credential tests, Ghost Archivist unit tests, SQL migration 003.
- **Test suite healthy**: `PYTHONPATH=. .venv/bin/pytest` → **312 passed, 5 skipped, 0 errors** (up from 295 — kingdonb's additional tests now included after sync).
- **kingdonb's async background sync landed**: `66396ee` ("feat(sync): implement async background sync and parallelized scraper") is now in our ancestry. Review it next session to see if it exposes new test gaps or bot-actionable work.
- **No open tagged issues**: kingdonb/mecris and yebyen/mecris both have zero issues tagged needs-test, pr-review, or bug.

## Verified This Session
- [x] **kingdonb/mecris#177 merged**: Confirmed closed at 17:22:11Z on 2026-04-09 (squash merge, 1 merge commit).
- [x] **Upstream sync complete**: `git merge upstream/main` (merge commit `5503f07`) — clean via 'ort' strategy, no conflicts.
- [x] **Full test suite still passes**: 312 passed, 5 skipped, 0 errors — no regressions from sync.

## Pending Verification (Next Session)
- [ ] **Explore kingdonb's async sync work**: Read `66396ee` ("feat(sync): implement async background sync and parallelized scraper") — understand what changed in Spin delegation and Home Server background tasks. Check if there are new test gaps or CI concerns from the Rust code.
- [ ] **Rust test gap (workflow fix)**: Modify `pr-test.yml` step `Run Rust tests` to check `[ -f Cargo.toml ]` before running `cargo test`. Needs `workflow` PAT scope — bot cannot push workflow changes. Needs kingdonb's action or a token with workflow scope.
- [ ] **Multiplier Sync Validation**: Verify setting the Review Pump lever in Android updates multiplier in Neon (`SELECT pump_multiplier FROM language_stats`). Requires live device + Neon access.
- [ ] **Ghost Archivist End-to-End**: Run scheduler locally, let archivist job fire, confirm logs show correct reconciliation without pushing fake data to Beeminder. (Unit tests complete; E2E still needs live environment.)
- [ ] **kingdonb/mecris#132 verification**: Trigger `/internal/failover-sync` and confirm `daily_completions` is non-zero in Neon if reviews were done.
- [ ] **kingdonb/mecris#127 manual close**: Bot cannot comment/close kingdonb issues (PAT scoped to yebyen only). kingdonb should close #127 as superseded by #132.
- [ ] **Android app has_goal UI**: Confirm Android app picks up `has_goal=false` flag and visually dims untracked languages. Requires live app test.
- [ ] **Majesty Cake Android integration**: `/aggregate-status` backend complete; Android app needs to consume it (kingdonb/mecris#170).
- [ ] **003_multi_tenancy.sql live run**: Run `psql $NEON_DB_URL -f scripts/migrations/003_multi_tenancy.sql` against live Neon.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope. Workflow file fixes must be committed by kingdonb or a token with `workflow` scope.
- **Fine-grained PAT**: `GITHUB_TOKEN` is scoped to yebyen/mecris only — cannot comment or close issues on kingdonb/mecris.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main resolves this automatically.
- **psycopg2 not installed in CI runner**: `test_presence_neon.py` may have pre-existing failures — not a regression.
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, ...)` + `patch("psycopg2.connect")` before importing. See `_make_mcp_importable()` in `test_mcp_server.py`.
- **Ghost Archivist lazy-import pattern**: `BeeminderClient` and `LanguageSyncService` are imported INSIDE `perform_archival_sync()` function body. Patch at source modules (`beeminder_client.BeeminderClient`, `services.language_sync_service.LanguageSyncService`), not at `ghost.archivist_logic`.
- **BeeminderClient note**: `UsageTracker.__init__` requires `NEON_DB_URL` even in the no-DB fallback path — mock UsageTracker when testing the env-var-only path.
- **Multi-tenancy schema**: `language_stats` PK is `(user_id, language_name)`; `budget_tracking` has `user_id UNIQUE`. All queries scope by user_id. SQL migration 003 formalizes this for live Neon.
- **pr-test workflow sets NEON_DB_URL** (line 93 of pr-test.yml): `postgresql://mecris:mecris@localhost:5432/mecrisdb`. This means conftest `pytest_ignore_collect` for NEON_DB_URL tests does NOT fire — those tests are collected and must not fail at import time.
- **requirements.txt Python dep chain**: `apscheduler>=3.10` (bfa0e75) + `SQLAlchemy>=2.0` (02b6340) — both needed because `scheduler.py` imports `SQLAlchemyJobStore` from apscheduler.
- **Upstream sync pattern**: `git remote add upstream https://github.com/kingdonb/mecris.git && git fetch upstream main && git merge upstream/main --no-edit` — clean via 'ort' strategy when histories diverge post-squash-merge.
