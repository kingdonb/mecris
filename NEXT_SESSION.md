# Next Session: Re-run pr-test for kingdonb/mecris#178 after test isolation fix push

## Current Status (2026-04-10)
- **PR open upstream**: kingdonb/mecris#178 from yebyen:main — 14 Rust unit tests + 3 cloud-sync Python tests + schema fix + test isolation fix. Not yet merged.
- **Test isolation fix committed**: `0fc0bf3` — `test_standalone_access.py` and `test_unauthorized_access.py` now use `_make_mcp_importable()` fixture pattern (sys.modules.pop + patch env + patch psycopg2.connect). Fix is LOCAL; push happens when this bot workflow ends.
- **yebyen/mecris 8+ commits ahead of kingdonb/mecris**: All commits in PR #178.
- **Rust test gap in pr-test.yml**: `Run Rust tests` step runs `cargo test` from repo root (no Cargo.toml there). Needs `workflow` PAT scope — bot cannot push workflow changes.

## Verified This Session
- [x] **pr-test dispatched twice**: Run 24241880849 — showed Python tests failing with `ForeignKeyViolation: budget_tracking_user_id_fkey` (new error, schema fix from 8597dbe worked but exposed FK issue). Run 24242162639 — still same error (fix 0fc0bf3 not yet pushed).
- [x] **Root cause identified**: `test_standalone_access.py:3` and `test_unauthorized_access.py:3` both imported `mcp_server` at module level. `mcp_server.py:249` creates `UsageTracker()` at import time → `_init_neon()` → INSERT into `budget_tracking` → FK violation (users table empty in CI).
- [x] **Fix committed as 0fc0bf3**: Both test files refactored to use `_make_mcp_importable()` pattern. Module-level import removed; mcp_server now imported inside fixture context with psycopg2 patched.

## Pending Verification (Next Session)
- [ ] **Re-run pr-test #178 after push**: Fix `0fc0bf3` must be on GitHub. After push (happens when this bot workflow ends), run `/mecris-pr-test 178` — expect Python collection errors to be gone. Watch for any new runtime test failures in `test_standalone_access.py` (standalone mode endpoint behavior).
- [ ] **PR kingdonb/mecris#178 merged**: Still open; needs green test run to motivate review.
- [ ] **Rust test gap (workflow fix)**: Modify `pr-test.yml` step `Run Rust tests` to use `working-directory: mecris-go-spin/sync-service`. Needs `workflow` PAT scope — bot cannot push workflow changes. Needs kingdonb's action.
- [ ] **test_narrator_context_standalone may fail at runtime**: The standalone test expects `/narrator/context` to return 200 with psycopg2 mocked. Endpoint may call external services (Beeminder, etc.) — check pr-test output carefully for runtime failures after collection is fixed.
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
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, ...)` + `patch("psycopg2.connect")` before importing. See `_make_mcp_importable()` in `test_mcp_server.py`, `test_cloud_sync.py`, `test_standalone_access.py`, `test_unauthorized_access.py`.
- **Ghost Archivist lazy-import pattern**: `BeeminderClient` and `LanguageSyncService` are imported INSIDE `perform_archival_sync()` function body. Patch at source modules, not at `ghost.archivist_logic`.
- **cloud-sync patch pattern**: `language_sync_service` is a module-level variable. Use `patch("mcp_server.language_sync_service")` AFTER importing mcp_server within env+psycopg2 patches.
- **BeeminderClient note**: `UsageTracker.__init__` requires `NEON_DB_URL` even in the no-DB fallback path — mock UsageTracker when testing the env-var-only path.
- **Multi-tenancy schema**: `language_stats` PK is `(user_id, language_name)`; `budget_tracking` has `user_id UNIQUE` with FK to `users(pocket_id_sub)`. All queries scope by user_id.
- **pr-test workflow sets NEON_DB_URL** (line 93 of pr-test.yml): `postgresql://mecris:mecris@localhost:5432/mecrisdb`. Tests that import mcp_server MUST patch psycopg2.connect or they will try to connect to the real local postgres and hit FK constraints.
- **schema.sql budget_tracking schema**: Fixed in `8597dbe` — columns are now `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE REFERENCES users(pocket_id_sub)`.
- **requirements.txt Python dep chain**: `apscheduler>=3.10` + `SQLAlchemy>=2.0` — both needed because `scheduler.py` imports `SQLAlchemyJobStore` from apscheduler.
- **Upstream sync pattern**: `git remote add upstream https://github.com/kingdonb/mecris.git && git fetch upstream main && git merge upstream/main --no-edit`.
- **Rust unit tests**: Pure functions extracted to module scope (`should_delegate`, `parse_forecast_count`, `arabic_completions`) — `cargo test` in `mecris-go-spin/sync-service/` runs 14 tests natively without Spin host.
