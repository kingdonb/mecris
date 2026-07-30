# Next Session: Observability & Android Failover

## Context
- **Last Session**: Akamai Spin API (`mecris-sync-v2` v64) restored to full Android sync readiness. First successful cloud walk sync since 2026-05-27.
- **Current State**:
  - **Akamai API**: All authenticated routes working (200 OK with valid Pocket ID token). Test walk ingested, Beeminder "bike" goal updated.
  - **Fermyon Cloud**: `mecris-sync-v2-r0r86pso.fermyon.app` → platform 404 (dead channel).
  - **Python MCP Server**: Still running locally but now a fallback; Akamai is the canonical production path.
  - **Android App**: Needs re-pointing to Akamai as default backend; failover behavior untested.

## High Priority Goals
1. **Add observability to Akamai deployment**
   - Log `extract_user_id` failures to Neon `events` table (per Observability Mandate)
   - Expose auth success/failure metric via `/internal/review-pump-status` or new `/internal/auth-health`
   - Alert on sustained 401/500 rate on protected routes

2. **Update `test_cloud_beta4_validation.py`**
   - Currently expects `/health` → 500 (outdated)
   - Now: `/health` with auth → 200, `/profile` → 200, `/walks` POST → 201
   - Add authenticated smoke test suite

3. **Android app: Point to Akamai + verify failover**
   - Update `spinBaseUrl` default to `https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app`
   - Test: Local Python server OFF → Android sync still works via Akamai
   - Test: Local ON → prefers local (lower latency), fails over to Akamai on error

4. **Prompt 1 pipeline: Deployment truth inventory**
   - Now that Akamai is verified, document the single canonical path
   - Fermyon Cloud: decommission or re-deploy if needed for redundancy

## Notes for the Narrator
- The walk was real — 2500 steps at 22:46 UTC, synced to Beeminder via Akamai Spin API.
- The Python MCP server has been doing all the work for 64 days while Akamai silently 401'd.
- Fermyon Cloud channel is dead; Akamai is the only live edge deployment.
- No code changes were needed — only runtime variable configuration.

## Files to Watch
- `mecris-go-spin/sync-service/spin.toml` — variable declarations
- `mecris-go-spin/sync-service/src/lib.rs` — `extract_user_id`, needs error telemetry
- `tests/test_cloud_beta4_validation.py` — outdated assertions
- `tests/test_cron_validation.py` — still valid, hits Akamai cron
- Android: `app/src/main/java/com/mecris/go/mesh/ServiceMeshClient.kt` (or equivalent)

---

*Session log updated: `session_log.md` (entry prepended)*
*Envelopes in `tlonbot/envelopes/1-7/PROMPT.md` ready for Prompt 1*