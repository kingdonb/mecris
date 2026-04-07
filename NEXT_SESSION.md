# Next Session: Multiplier Sync Validation (Review Pump lever → Neon DB)

## Current Status (2026-04-07)
- **Ghost Archivist continuous reconciliation DONE**: `should_ghost_wake_up` now uses idempotency-only (12h cooldown); night-window (2-5 AM UTC) and human-silence checks removed per SYS-001 spec.
- **DEFECT-003 confirmed resolved**: `perform_archival_sync` does not push 0.0 to Beeminder `bike` goal.
- **All archivist tests passing**: 7/7 pass (`test_archivist_logic.py`, `test_archivist_wakeup.py`).
- **yebyen/mecris in sync with kingdonb/mecris**: Both at commit `219130b` before this session's work.
- **Rust WASM components merged**: Review Pump Core, Nag Ladder, Majesty Cake all merged into main.

## Verified This Session (2026-04-07)
- [x] **Ghost Archivist refactor**: `should_ghost_wake_up` is now a pure idempotency check — no time-of-day restriction, no human presence gating.
- [x] **test_archivist_logic.py updated**: Old tests verified the banned behavior (night window, human silence). New tests verify correct spec-compliant behavior.
- [x] **DEFECT-003 already resolved**: Confirmed by reading `perform_archival_sync` — no `beeminder_client.add_datapoint("bike", 0.0, ...)` call present.
- [x] **Commit landed**: `9497663 refactor: implement Ghost Archivist continuous reconciliation (SYS-001)`.

## Pending Verification (Next Session)
- [ ] **Multiplier Sync Validation**: Verify that setting the Review Pump lever in the Android app correctly updates the multiplier in Neon (`SELECT pump_multiplier FROM language_stats`). Requires live device + Neon access.
- [ ] **Ghost Archivist End-to-End**: Run the scheduler locally, let the archivist job fire, and confirm via logs that it correctly reconciles state without pushing fake data to Beeminder. The code is correct; the live verification is still needed.
- [ ] **kingdonb/mecris#127 disposition**: "Cloud: Failover" investigation issue has no body and zero comments. Determine if it is superseded by #132 (already shows "Verification Needed") or still open work.
- [ ] **kingdonb/mecris#132 verification**: The failover sync Rust implementation needs live verification — trigger `/internal/failover-sync` and confirm `daily_completions` is non-zero in Neon if reviews were done.

## Infrastructure Notes
- Spin Cron trigger is **DISABLED** in `spin.toml` — do not re-enable.
- `MECRIS_MODE=standalone` bypasses JWKS for local dev; `MECRIS_MODE=cloud` enforces RSA verification + issuer check.
- `MASTER_ENCRYPTION_KEY` must be a 64-char hex string (32-byte AES-256 key).
- **Classic PAT scope**: `GITHUB_CLASSIC_PAT` has `repo` scope ONLY — no `workflow` scope. Workflow file fixes must be committed by kingdonb or a token with `workflow` scope.
- **NEXT_SESSION.md merge conflict is permanently fixed**: `.gitattributes merge=union` on yebyen/mecris:main resolves this automatically.
- **psycopg2 not installed in CI runner**: `test_presence_neon.py` has 13 pre-existing failures due to missing DB driver — not a regression.
