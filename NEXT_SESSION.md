# Next Session: kingdonb review and merge of kingdonb/mecris#178 (Python CI green)

## Current Status (2026-04-10)
- **PR open upstream**: kingdonb/mecris#178 from yebyen:main — 14 Rust unit tests + 3 cloud-sync Python tests + schema fixes + test isolation fixes. Not yet merged.
- **Python CI fully green**: pr-test run 24252329711 — 321 passed, 4 skipped, 0 failures. Up from 318 passed / 3 failed.
- **Android CI green**: unchanged from prior sessions.
- **Rust CI still failing**: Known; `pr-test.yml` runs `cargo test` in wrong directory. Needs `workflow` PAT scope to fix — bot cannot push workflow file changes.
- **yebyen/mecris ahead of kingdonb/mecris**: All divergence is in PR #178.

## Verified This Session
- [x] **pr-test #178 Python tests fully green**: run 24252329711 — 321 passed, 4 skipped, 0 failures.
  - `test_autonomous_tables_exist` ✅ (token_bank now in schema.sql)
  - `test_global_walk_sync_job_success` ✅ (mcp_server import isolation)
  - `test_global_walk_sync_job_skips_when_not_leader` ✅ (mcp_server import isolation)
- [x] **yebyen/mecris#138 closed**: plan issue from previous session, closed after CI confirmed green.
- [x] **No upstream sync needed**: `b31cfa9` (kingdonb docs fix) is already in yebyen/mecris history.

## Pending Verification (Next Session)
- [ ] **PR kingdonb/mecris#178 merged**: Python + Android are green. Rust is a known pre-existing gap (wrong Cargo.toml path in workflow). Needs kingdonb review and merge.
- [ ] **Rust test gap (workflow fix)**: Modify `pr-test.yml` step `Run Rust tests` to use `working-directory: mecris-go-spin/sync-service`. Needs `workflow` PAT scope — bot cannot push workflow changes. Needs kingdonb's action.
- [ ] **test_narrator_context_standalone may fail at runtime**: The standalone test expects `/narrator/context` to return 200 with psycopg2 mocked. Monitor for runtime failures in future pr-test runs.
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
- **Test isolation pattern**: Tests that import `mcp_server` must use `sys.modules.pop("mcp_server", None)` + `patch.dict(os.environ, ...)` + `patch("psycopg2.connect")` before importing. See `_make_mcp_importable()` in `test_mcp_server.py`, `test_cloud_sync.py`, `test_standalone_access.py`, `test_unauthorized_access.py`, `test_walk_sync.py`.
- **Ghost Archivist lazy-import pattern**: `BeeminderClient` and `LanguageSyncService` are imported INSIDE `perform_archival_sync()` function body. Patch at source modules, not at `ghost.archivist_logic`.
- **cloud-sync patch pattern**: `language_sync_service` is a module-level variable. Use `patch("mcp_server.language_sync_service")` AFTER importing mcp_server within env+psycopg2 patches.
- **BeeminderClient note**: `UsageTracker.__init__` requires `NEON_DB_URL` even in the no-DB fallback path — mock UsageTracker when testing the env-var-only path.
- **Multi-tenancy schema**: `language_stats` PK is `(user_id, language_name)`; `budget_tracking` has `user_id UNIQUE` with FK to `users(pocket_id_sub)`. All queries scope by user_id.
- **pr-test workflow sets NEON_DB_URL** (line 93 of pr-test.yml): `postgresql://mecris:mecris@localhost:5432/mecrisdb`. Tests that import mcp_server MUST patch psycopg2.connect or they will try to connect to the real local postgres and hit FK constraints.
- **schema.sql budget_tracking schema**: Fixed in `8597dbe` — columns are now `budget_period_start TEXT NOT NULL`, `budget_period_end TEXT NOT NULL`, `total_budget DOUBLE PRECISION NOT NULL`, `remaining_budget DOUBLE PRECISION NOT NULL`, `user_id UNIQUE REFERENCES users(pocket_id_sub)`.
- **schema.sql token_bank**: Added in `c88d368` — `CREATE TABLE IF NOT EXISTS token_bank (user_id TEXT PRIMARY KEY REFERENCES users(pocket_id_sub), available_tokens BIGINT NOT NULL DEFAULT 0, monthly_limit BIGINT NOT NULL DEFAULT 1000000, last_refill TIMESTAMPTZ NOT NULL DEFAULT NOW())`.
- **requirements.txt Python dep chain**: `apscheduler>=3.10` + `SQLAlchemy>=2.0` — both needed because `scheduler.py` imports `SQLAlchemyJobStore` from apscheduler.
- **Upstream sync pattern**: `git remote add upstream https://github.com/kingdonb/mecris.git && git fetch upstream main && git merge upstream/main --no-edit`.
- **Rust unit tests**: Pure functions extracted to module scope (`should_delegate`, `parse_forecast_count`, `arabic_completions`) — `cargo test` in `mecris-go-spin/sync-service/` runs 14 tests natively without Spin host.
- **pr-test.yml push constraint**: Bot dispatches pr-test but local commits are not on GitHub until bot workflow ends. Do NOT dispatch pr-test expecting to see local commits — always dispatch AFTER the push (i.e., in the NEXT session after commits land).
