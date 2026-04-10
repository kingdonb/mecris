# Next Session: Re-run pr-test for kingdonb/mecris#178 after schema fix push

## Current Status (2026-04-10)
- **PR open upstream**: kingdonb/mecris#178 from yebyen:main — 14 Rust unit tests + 3 cloud-sync Python tests. Not yet merged.
- **Schema bug found and fixed**: `mecris-go-spin/schema.sql` had `period_start`/`period_end` columns in `budget_tracking`; `usage_tracker.py` expects `budget_period_start`/`budget_period_end`. Fix committed as `8597dbe` but NOT yet pushed — pr-test was still failing when the session ended.
- **yebyen/mecris 5 commits ahead of kingdonb/mecris**: Commits 26735a1–8597dbe in PR #178 + schema fix commit.
- **Rust test gap in pr-test.yml**: `Run Rust tests` step runs `cargo test` from repo root (no Cargo.toml there). Needs `workflow` PAT scope to fix — bot cannot push workflow changes.

## Verified This Session
- [x] **pr-test dispatched for kingdonb/mecris#178**: Run 24226175715 completed; Android ✅, Python ❌ (schema bug), Rust ❌ (known Cargo.toml path issue)
- [x] **Root cause identified**: `initialize_neon.py` runs `schema.sql` first in CI, creating `budget_tracking` without `budget_period_start`; `CREATE TABLE IF NOT EXISTS` in `_init_neon()` is then a no-op; INSERT fails
- [x] **Schema fix committed**: `8597dbe` updates `budget_tracking` in `schema.sql` to use `budget_period_start TEXT NOT NULL`/`budget_period_end TEXT NOT NULL` + `UNIQUE` on `user_id` + `DOUBLE PRECISION` for budget columns — matching `usage_tracker.py`

## Pending Verification (Next Session)
- [ ] **Re-run pr-test #178 after push**: Schema fix commit `8597dbe` must be on GitHub for pr-test to pick it up. After session push lands on `yebyen/mecris:main`, run `/mecris-pr-test 178` — expect Python tests to pass this time.
- [ ] **PR kingdonb/mecris#178 merged**: Check if kingdonb has reviewed and merged; if not, pr-test green result will motivate review.
- [ ] **Rust test gap (workflow fix)**: Modify `pr-test.yml` step `Run Rust tests` to check `[ -f Cargo.toml ]` or use `working-directory: mecris-go-spin/sync-service`. Needs `workflow` PAT scope — bot cannot push workflow changes. Needs kingdonb's action.
- [ ] **test_standalone_access.py / test_unauthorized_access.py behavior after schema fix**: Once schema is corrected, these tests will be collected and actually RUN (not just fail at import). They may expose new failures — check pr-test output carefully.
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
- **Python venv not present in bot runner**: `PYTHONPATH=. .venv/bin/pytest` cannot run in bot context; Python tests validated via kingdonb/mecris pr-test workflow instead.
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, ...)` + `patch("psycopg2.connect")` before importing. See `_make_mcp_importable()` in `test_mcp_server.py`.
- **Ghost Archivist lazy-import pattern**: `BeeminderClient` and `LanguageSyncService` are imported INSIDE `perform_archival_sync()` function body. Patch at source modules (`beeminder_client.BeeminderClient`, `services.language_sync_service.LanguageSyncService`), not at `ghost.archivist_logic`.
- **cloud-sync patch pattern**: `language_sync_service` is a module-level variable. Use `patch("mcp_server.language_sync_service")` AFTER importing mcp_server within env+psycopg2 patches — see `tests/test_cloud_sync.py`.
- **BeeminderClient note**: `UsageTracker.__init__` requires `NEON_DB_URL` even in the no-DB fallback path — mock UsageTracker when testing the env-var-only path.
- **Multi-tenancy schema**: `language_stats` PK is `(user_id, language_name)`; `budget_tracking` has `user_id UNIQUE`. All queries scope by user_id. SQL migration 003 formalizes this for live Neon.
- **pr-test workflow sets NEON_DB_URL** (line 93 of pr-test.yml): `postgresql://mecris:mecris@localhost:5432/mecrisdb`. This means conftest `pytest_ignore_collect` for NEON_DB_URL tests does NOT fire — those tests are collected and must not fail at import time.
- **schema.sql budget_tracking schema**: Fixed in `8597dbe` — columns are now `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE`. Rust code does not reference these columns.
- **requirements.txt Python dep chain**: `apscheduler>=3.10` (bfa0e75) + `SQLAlchemy>=2.0` (02b6340) — both needed because `scheduler.py` imports `SQLAlchemyJobStore` from apscheduler.
- **Upstream sync pattern**: `git remote add upstream https://github.com/kingdonb/mecris.git && git fetch upstream main && git merge upstream/main --no-edit` — clean via 'ort' strategy when histories diverge post-squash-merge.
- **Rust unit tests**: Pure functions extracted to module scope (`should_delegate`, `parse_forecast_count`, `arabic_completions`) — `cargo test` in `mecris-go-spin/sync-service/` runs 14 tests natively without Spin host.
