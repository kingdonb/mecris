# Next Session: Explore further bot-actionable test gaps or open new health-report work

## Current Status (2026-04-09)
- **yebyen/mecris fully synced with kingdonb/mecris**: `git log HEAD..upstream/main` is empty.
- **Rust unit tests added**: `mecris-go-spin/sync-service/src/lib.rs` now has 14 passing unit tests (commit 93bc2c0). `cargo test` confirmed viable for Spin WASM crate on native target.
- **Test suite healthy**: `PYTHONPATH=. .venv/bin/pytest` → **315 passed, 5 skipped, 0 errors** (Python; venv not available in bot runner, but no regressions from Rust-only change).
- **No open tagged issues**: kingdonb/mecris and yebyen/mecris both have zero issues tagged needs-test, pr-review, or bug.
- **Bot PAT limitations remain**: `GITHUB_CLASSIC_PAT` has repo scope only (no workflow scope); `GITHUB_TOKEN` scoped to yebyen/mecris only.

## Verified This Session
- [x] **Rust test gap from 66396ee closed**: 14 unit tests covering `should_delegate`, `parse_forecast_count`, `arabic_completions` — all passing via `cargo test` in `mecris-go-spin/sync-service/`.
- [x] **`cargo test` is viable for Spin WASM crate**: Spin SDK does NOT block native compilation for unit tests. No `rlib` hack needed; `cdylib` crate-type is sufficient.
- [x] **Plan issue yebyen/mecris#134 created, commented, closed**: audit trail complete.

## Pending Verification (Next Session)
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
- **Python venv not present in bot runner**: `PYTHONPATH=. .venv/bin/pytest` cannot run in bot context; Python tests validated via kingdonb/mecris pr-test workflow instead.
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, ...)` + `patch("psycopg2.connect")` before importing. See `_make_mcp_importable()` in `test_mcp_server.py`.
- **Ghost Archivist lazy-import pattern**: `BeeminderClient` and `LanguageSyncService` are imported INSIDE `perform_archival_sync()` function body. Patch at source modules (`beeminder_client.BeeminderClient`, `services.language_sync_service.LanguageSyncService`), not at `ghost.archivist_logic`.
- **cloud-sync patch pattern**: `language_sync_service` is a module-level variable. Use `patch("mcp_server.language_sync_service")` AFTER importing mcp_server within env+psycopg2 patches — see `tests/test_cloud_sync.py`.
- **BeeminderClient note**: `UsageTracker.__init__` requires `NEON_DB_URL` even in the no-DB fallback path — mock UsageTracker when testing the env-var-only path.
- **Multi-tenancy schema**: `language_stats` PK is `(user_id, language_name)`; `budget_tracking` has `user_id UNIQUE`. All queries scope by user_id. SQL migration 003 formalizes this for live Neon.
- **pr-test workflow sets NEON_DB_URL** (line 93 of pr-test.yml): `postgresql://mecris:mecris@localhost:5432/mecrisdb`. This means conftest `pytest_ignore_collect` for NEON_DB_URL tests does NOT fire — those tests are collected and must not fail at import time.
- **requirements.txt Python dep chain**: `apscheduler>=3.10` (bfa0e75) + `SQLAlchemy>=2.0` (02b6340) — both needed because `scheduler.py` imports `SQLAlchemyJobStore` from apscheduler.
- **Upstream sync pattern**: `git remote add upstream https://github.com/kingdonb/mecris.git && git fetch upstream main && git merge upstream/main --no-edit` — clean via 'ort' strategy when histories diverge post-squash-merge.
- **Rust unit tests**: Pure functions extracted to module scope (`should_delegate`, `parse_forecast_count`, `arabic_completions`) — `cargo test` in `mecris-go-spin/sync-service/` runs 14 tests natively without Spin host.
