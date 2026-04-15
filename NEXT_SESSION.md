# Next Session: Verify new handler tests (≥437 Python) via pr-test; await kingdonb merge of PR #182

## Current Status (2026-04-15)
- **Akamai Functions Deployment (Trial)**: `sync-service` deployed to Akamai (`394b84e7-760c-4336-975b-653c17fdb446`).
- **Cron Jobs Active**: `trigger-reminders` (2h), `failover-sync-edt` (04:05 UTC), `failover-sync-est` (05:05 UTC).
- **PR #182 open on kingdonb/mecris** (yebyen:main → kingdonb:main): Twilio webhook Phase 2 + satellite crate tests + gauge type + CredentialsManager tests + update_pump_multiplier tests + HealthChecker tests + BeeminderClient.add_datapoint tests + mcp_server handler tests. Awaiting kingdonb review/merge.
- **pr-test confirmed green at HEAD `e8130a7` (PR #182 baseline)**: 423 Python ✅, 91 Rust ✅, Android ✅. Run: https://github.com/yebyen/mecris/actions/runs/24470904515
- **yebyen/mecris is 15 commits ahead of kingdonb/mecris**: all in PR #182 plus new commit `a566629`.
- **New commit `a566629`** — 14 unit tests for mcp_server.py handler functions. Expected Python count: **437**.
- **Satellite crate tests (147 total)**: In code but NOT yet in CI — requires workflow PAT fix (yebyen/mecris#142).

## Verified This Session
- [x] **Akamai Deployment Success**: `sync-service` live with live Neon/Twilio/Weather variables.
- [x] **Akamai Cron Scheduling**: 3 jobs active via `spin aka cron create`.
- [x] **pr-test green at baseline `e8130a7`**: 423 Python (4 skipped), 91 Rust, Android BUILD SUCCESSFUL.
- [x] **14 new mcp_server handler tests committed** at `a566629`.
- [x] **Added `/internal/failover-sync` route** to `sync-service` for unauthenticated cron triggers.

## Pending Verification (Next Session)
- [ ] **Confirm Akamai cron jobs firing**: Check Akamai logs to determine if `trigger-reminders`, `failover-sync-edt`, and `failover-sync-est` are executing correctly.
- [ ] **Akamai E2E Logic Test**: Manually `POST` to `/internal/failover-sync` and `/internal/trigger-reminders` on the Akamai endpoint to verify cloud behavior.
- [ ] **Security Hardening (Akamai)**: Address the unauthenticated `/internal/*` endpoints. Currently open for experimentation but needs an API key or IP whitelist.
- [ ] **Dispatch pr-test for PR #182 to verify Python count ≥ 437**: `a566629` is now on GitHub after bot workflow push. Run pr-test and confirm new baseline.
- [ ] **Confirm PR #182 merged by kingdonb**: check kingdonb/mecris main for commits up to `a566629`.
- [ ] **Run 004_user_location.sql against live Neon**: `psql $NEON_DB_URL -f scripts/migrations/004_user_location.sql`.
- [ ] **Twilio webhook Phase 2 live E2E**: Requires Twilio variables in Fermyon Cloud.
- [ ] **Multi-Tenancy — Android UI Gaps**: Add "log out" button, phone/location settings, preferred health source. Tracked in kingdonb/mecris#168.
- [ ] **Rust test gap (workflow fix)**: Apply fix from yebyen/mecris#142. Needs `workflow` PAT.
- [ ] **Multiplier Sync Validation**: Verify setting the Review Pump lever in Android updates multiplier in Neon.

## Infrastructure Notes
- **Akamai Functions (Trial)**: Persistent cron triggers for reminders and failover syncing.
  - `/internal/failover-sync` (POST): Unauthenticated sync for cron.
  - `/internal/trigger-reminders` (POST): Unauthenticated reminder evaluation for cron.
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main.
- **Rust satellite crates**: 158 tests total across 6 crates (sync-service 91, boris-fiona-walker 28, others 39).
- **Akamai Next Run**: 22:00 UTC (trigger-reminders), 04:05 UTC (failover-sync-edt), 05:05 UTC (failover-sync-est).
