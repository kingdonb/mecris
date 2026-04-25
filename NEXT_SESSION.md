# Next Session: Resolve Cloud Readiness Gap & Align Release Management

## Current Status (2026-04-24, post-session #47)
- **Spin SDK v4 Migration COMPLETE (Local)**: All 4 Python WASM components successfully migrated to the modern **Wasm Component Model**. Verified functional on port 3001 using `spin up`.
- **"Universal Clean Build" Strategy ESTABLISHED**: Standardized `spin.toml` with isolated, `uv`-managed build commands. Prevents environment pollution and standard library (datetime) missing module errors.
- **"Observant Presence" IMPLEMENTED**: Bot no longer skips tasks when human is present; instead logs presence and continues, surfacing a **"Ghost Heartbeat"** in the `mecris pulse` dashboard.
- **Fermyon/Akamai Cloud Gap IDENTIFIED**: Despite local success, cloud runtimes currently return `NotImplementedError` or `500 (guest not invoked)` with the new SDK v4 binaries (released ~20 hours ago).

## Verified This Session
- [x] **SDK v4 Migration**: `review-pump-py`, `budget-governor-py`, `arabic-skip-counter`, `log-message-py` all use `http.Handler` and `async def handle_request`.
- [x] **Isolated Builds**: All WASM files built with dedicated `uv venv --clear` in `spin.toml`.
- [x] **Postgres Driver**: `arabic-skip-counter` uses `spin_sdk.postgres` instead of `psycopg2`.
- [x] **Observant Presence**: Scheduler registers jobs even when human is present; logs "observant mode".
- [x] **Ghost Heartbeat**: `mecris pulse` dashboard shows bot activity age in recommendations.

## Pending Verification

### 👤 Human-required (cannot be resolved by bot)
- [ ] **Cloud Readiness Check**: Monitor Fermyon/Akamai for updates to their Python WASM runtimes. Test a simple SDK v4 "Hello World" to confirm when the platform has caught up.
- [ ] **Align Release Management**: Determine if we should maintain a "Legacy Cloud" branch or implement a compatibility shim until the cloud catch-up is complete.
- [ ] **Verify log-message-py in Cloud**: Once platforms are ready, confirm audit logs appear in cloud KV.

### 🤖 Bot-actionable (can be resolved in future sessions)
- [ ] **Backport "Majesty Cake" Momentum Visualizer (kingdonb/mecris#195)**: (Carry forward) Pulsing orb with "Majesty Rings".
- [ ] **Port Twilio to WASM Brain (Issue #167)**: (Carry forward) Move SMS/WhatsApp dispatch logic to Rust.
- [ ] **Rust Reminder Engine (Issue #169)**: (Carry forward) Native Rust implementation of reminders.

## Infrastructure Notes (carried forward)
- **Universal Clean Build Strategy**: `find . -name '.venv*' -type d -exec rm -rf {} + && find . -name '__pycache__' -type d -exec rm -rf {} + && uv venv .venv_build --clear --python 3.13 && . .venv_build/bin/activate && uv pip install componentize-py==0.23.0 spin-sdk==4.0.0 && componentize-py -w spin:up/http-trigger@4.0.0 componentize -p . -p .venv_build/lib/python3.13/site-packages app -o component.wasm`
- **SDK v4 async mandate**: `variables.get`, `kv.open_default`, `store.get`, `postgres.query`, and `http.send` are all **async** in SDK 4.0.0.
- **Observant Presence logic**: `is_human_present` checks `/tmp/mecris_presence.lock` and `pgrep -f cli.main`. Logs but does not block registration in `MecrisScheduler`.
- **HCAT sandbox image**: `docker/hcat.Dockerfile` updated with `python3-modules` for stdlib completeness.
