# Session Log: AppAuth Sticky Error-Lock Resolution & Release Lockfile Parity

**Date:** 2026-08-19  
**Branch:** `fix/appauth-state-reset` (PR #289)  
**Primary Model:** Gemini 3.7 Flash  
**Human:** yebyen  

---

## Summary

1. **AppAuth Error-Lock Fixed**: Investigated live ADB logcat traces showing `W AppAuth: AuthState.update should not be called in an error state`. Fixed `PocketIdAuthRepository.kt` to instantiate a fresh `AppAuthAuthState(resp, ex)` on passkey authorization, wiping any previous sticky `invalid_grant` error-lock state.
2. **`uv.lock` Release Parity Plan & Implementation**: Identified why `uv.lock` drifted during the `0.0.1` release (`bump_version.py` updated `pyproject.toml` without running `uv lock`). Automated `uv lock` in `scripts/bump_version.py` and updated `docs/RELEASE_PROCESS.md` and `/release-workflow` skills to include `uv.lock` in version definitions and git staging.

---

# Session Log: Akamai API Restored — Android Sync Unblocked

**Date:** 2026-07-30  
**Branch:** `main`  
**Primary Model:** nemotron-3-ultra-550b-a55b:free (via OpenRouter) + Pi coding agent  
**Human:** yebyen

---

## Summary

Restored the **Akamai-deployed Spin API (`mecris-sync-v2`)** to full Android sync readiness. The deployment was live but **authentication was broken** — all OIDC-protected routes returned 401/500 because the `oidc_jwks_json` Spin variable was never set on the Akamai Functions deployment. After setting the variable and redeploying, the canonical API contract is fully operational: `/profile`, `/aggregate-status`, `/languages`, `/budget`, `/walks` POST, `/internal/cloud-sync` all return 200 with valid Pocket ID tokens. A test walk was ingested, aggregate status updated, and Beeminder "bike" goal synced (first successful cloud walk sync since 2026-05-27).

---

## Problem

The `mecris-sync-v2` app on Akamai Functions (ID: `394b84e7-760c-4336-975b-653c17fdb446`, URL: `https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app`) had been deployed since 2026-05-27 (v62) but **OIDC verification failed silently**:

- `/internal/review-pump-status` (public) → 200 OK
- `/health` (unauthenticated) → 200 OK but weak signal
- **All authenticated routes** (`/profile`, `/aggregate-status`, `/languages`, `/budget`, `/walks`, `/internal/cloud-sync`) → **401 Unauthorized** (with valid token) or **500 Internal Server Error** (missing JWKS caused panic in `extract_user_id`)

The Android app could not complete its sync contract against Akamai, forcing reliance on the local Python MCP server (which had its own latency/availability issues).

**Root cause:** `extract_user_id` in `sync-service/src/lib.rs` requires `oidc_jwks_json` variable to verify RS256 tokens. This variable was defined in `spin.toml` but **never set on the Akamai deployment**.

---

## Solution

### 1. Diagnosed via authenticated smoke tests + `spin aka logs`

Confirmed the deployment was healthy (cron triggers firing globally, DB reachable) but OIDC verification path was broken. The JWKS from Pocket ID (`https://metnoom.urmanac.com/.well-known/jwks.json`) has kid `tmUpnrhx6gk`, matching the issued tokens.

### 2. Set all required Spin variables and redeployed

```bash
cd mecris-go-spin/sync-service
spin aka deploy --build --no-confirm --skip-readiness-check \
  --variable db_url="postgresql://neondb_owner:****@ep-weathered-hat-.../neondb?sslmode=require&channel_binding=require" \
  --variable neon_db_url="postgresql://neondb_owner:****@ep-weathered-hat-.../neondb?sslmode=require&channel_binding=require" \
  --variable master_encryption_key="****" \
  --variable internal_api_key="test-internal-key" \
  --variable clozemaster_email="kingdon@tuesdaystudios.com" \
  --variable clozemaster_password="****" \
  --variable twilio_account_sid="****" \
  --variable twilio_auth_token_encrypted="****" \
  --variable twilio_from_number="+15744757115" \
  --variable openweather_api_key="****" \
  --variable oidc_jwks_json='{"keys":[{"alg":"RS256","e":"AQAB","kid":"tmUpnrhx6gk","kty":"RSA","n":"vqLb33vkC8oZ7NDdlcBfBztPOAue3ZWrMDNhk9fBU2xrX6WTiAofqGDe_JJDCywJfEyDY-ecfQEXc5pph4v9R5xRiGhel4hLfcdcUTV7FH6MehaufcTREh_khCuAhyMOvUNlhw63mTY0yDpmaHubkh8vyhJUvmzBxr1ZR2snnrbas9q_ASvhKBeinFiAwXYH7Jf8I6C7E5LjP4BO4_ft4P2KBdspKSSREgln_i-ntZCt0UgLgDcS5coNGrz8hw-3NLUKAgHG_5GFXKSuibTV86Esk6MSYSgtKdHLM4O59Hgyz4CPFI8s47jtsLbbpuo8nq-WHU1PtQoTE1IayAD0tQ","use":"sig"}]}' \
  --variable cloud_provider="akamai"
```

Deployed as **v64** (2026-07-30 19:16:38 UTC).

### 3. Verified full Android sync contract

| Route | Auth | Status |
|-------|------|--------|
| `/health` | Bearer | ✅ 200 |
| `/profile` | Bearer | ✅ 200 |
| `/aggregate-status` | Bearer | ✅ 200 `walk: true` |
| `/languages` | Bearer | ✅ 200 6 languages |
| `/budget` | Bearer | ✅ 200 |
| `/walks` POST | Bearer | ✅ 201 walk ingested |
| `/internal/cloud-sync` POST | Bearer | ✅ 200 |
| `/internal/failover-sync` POST | x-internal-api-key | ✅ 200 |

**Beeminder verification:** Walk synced to "bike" goal — datapoint for 2026-07-30 shows `Value: 1.0, Comment: "Synced via Spin (Cumulative)"`. First successful cloud walk sync since **2026-05-27**.

---

## Files Changed

No code changes — only runtime configuration via `spin aka deploy --variable`. The `spin.toml` already declares all required variables.

---

## Key Learnings

1. **`oidc_jwks_json` is mandatory for OIDC on Akamai** — The Spin SDK's `jwt_simple` verification requires the JWKS at runtime. Without it, `extract_user_id` returns `None` → 401/500 on all protected routes.

2. **`spin aka logs` shows request routing but not app-level errors** — The logs showed cron triggers hitting `/internal/trigger-reminders` globally (20+ edge regions), but 500s from missing JWKS don't appear in access logs. Need structured error logging to Neon `events` table (per Observability Mandate).

3. **Fermyon Cloud channel is dead** — `mecris-sync-v2-r0r86pso.fermyon.app` returns platform 404. Akamai (`fwf.app`) is the only live deployment.

4. **Python MCP server was a crutch** — Its latency and availability issues masked the fact that the *canonical* Spin API was one variable away from working.

5. **Android sync contract is minimal and working** — Only `/walks`, `/aggregate-status`, `/languages`, `/budget`, `/internal/cloud-sync` needed. All now 200 OK.

---

## Attribution

**Diagnosis & deployment:** Pi coding agent (earendil-works/pi-coding-agent) + nemotron-3-ultra
**Human direction, credentials, Android verification:** yebyen
**Mecris framework:** kingdonb/mecris (Gall-loop skills, MCP tools)

---

## Previous Session Log: Unified MCP stdio + HTTP Bridge for Mecris

**Date:** 2026-07-19
**Branch:** `feat/unified-mcp-http-bridge`
**Primary Model:** nemotron-3-ultra-550b-a55b:free (via OpenRouter)
**Human:** yebyen

---

## Summary

Consolidated the Mecris MCP server into a **single process** that serves both:
- **stdio MCP** → Pi coding agent (and other stdio clients)
- **HTTP bridge on :8080** → Android app (walk uploads, heartbeats)

Eliminated the need for manual `tmux` sessions, duplicate schedulers, and port conflicts.

---

## Problem

The Mecris architecture had two separate entry points:
1. `mcp_stdio_server.py` — for Pi/stdin clients (no HTTP)
2. `mcp_server.py` — for HTTP/Android (no stdio MCP)

This caused:
- **Port 8080 conflicts** when both ran
- **Two schedulers** (race conditions on Neon leader election)
- **Manual tmux** required to keep HTTP bridge alive
- **Silent failures** — Pi extension ignored stderr, hid startup crashes

---

## Solution

### 1. `mcp_server.py` — Single Canonical Entry Point

```python
# Always starts HTTP thread (daemon) on :8080
http_thread = threading.Thread(target=run_http_server, daemon=True)
http_thread.start()

if "--stdio" in sys.argv:
    # Trust the flag — Pi's StdioClientTransport provides a pipe
    asyncio.run(run_stdio_with_scheduler())
else:
    # Interactive/background: keep process alive for HTTP
    signal.pause()
```

**Key behaviors:**
- HTTP thread starts **immediately** (before stdio logic)
- `--stdio` flag **overrides** stdin detection — always runs MCP server
- After stdio client disconnects: process **stays alive** (HTTP bridge persists)
- Rich stderr logging: `[MECRIS MAIN] ...` for debugging

### 2. `.pi/extensions/mecris/index.ts` — Robust Connection

```typescript
// Capture Python stderr to surface import/startup errors
transport = new StdioClientTransport({
  command: resolvePython(),
  args: [STDIO_SCRIPT, "--stdio"],
  cwd: MECRIS_HOME,
  env: { ...process.env, PYTHONPATH: MECRIS_HOME },
  stderr: "pipe",  // was "ignore"
});

if (transport.stderr) {
  transport.stderr.on("data", (chunk) => {
    stderrOutput += chunk.toString();
  });
}
```

**Improvements:**
- `stderr: "pipe"` + event handler → errors visible in Pi notifications
- Spawns `mcp_server.py --stdio` (not old `mcp_stdio_server.py`)
- `/mecris-reconnect` command for live recovery
- Lazy-loading: core tools active, rest via `mecris_load_tools`

---

## Files Changed

| File | Purpose |
|------|---------|
| `mcp_server.py` | Unified stdio + HTTP server; `--stdio` flag; survives client disconnect |
| `.pi/extensions/mecris/index.ts` | Captures stderr; spawns unified server; lazy tool loading |

---

## Commits

```
bfdbc38 fix: Ensure MCP stdio + HTTP bridge runs as single process
ed6f856 fix: Read Python stderr asynchronously to avoid blocking Pi startup
1507744 fix: Scope stderrOutput outside try/catch block
```

---

## Verification

```bash
# 1. Start Pi with extension
pi -e ./.pi/extensions/mecris/index.ts --continue

# 2. Health check (HTTP bridge)
curl -s http://127.0.0.1:8080/health
# {"status":"healthy","home_server_active":true,"neon_connected":true,...}

# 3. MCP tool call (via Pi)
# > Call mecris_get_narrator_context
# ✓ Returns full context with Android pulse, budget, goals

# 4. Android app: Settings → Backend → "Local (Python: 8080)"
#    Walk sync → Cloud Sync: Success
```

---

## Attribution

**Architecture & implementation:** nemotron-3-ultra-550b-a55b:free (via OpenRouter)
**Human direction, testing, integration:** yebyen
**Pi harness integration:** Pi coding agent (earendil-works/pi-coding-agent)
**Mecris framework:** kingdonb/mecris (Gall-loop skills, MCP tools)

---

## Next Steps

- [ ] Android app: verify failover to cloud (Akamai/Fermyon) when local down
- [ ] Add structured logging to HTTP thread (file + stdout)
- [ ] Consider systemd/service management for headless deployments
- [ ] Document COZYBEBY operational model in `docs/COZYBEBY.md`