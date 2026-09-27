# Session Log: Subnet Roaming Auth Resilience, MikroTik Isolation Audit & MCP Python 3.13 Sync

**Date:** 2026-09-26  
**Human:** yebyen  
**Primary Agent:** Gemini 3.1 Pro / Gemini 3.8 Flash (Antigravity pair)  
**Symptom:**
1. Android app (`com.mecris.go`) stuck in an auth bounce loop / failing passkey authentication and dropping to unauthenticated state when roaming between the 14-net and 13-net (`SocketTimeoutException` connecting to Pocket-ID at `10.17.13.140:443`).
2. Suspicion of AP client isolation on the MikroTik router (`10.17.13.249`).
3. Local MCP Server failing to start with `ModuleNotFoundError: No module named 'dotenv'` due to an unpopulated `.venv`.

---

## 1. Summary

During this session, we accomplished three core milestones:
1. **Hardened Android OIDC Authentication against Subnet Roaming:** 
   Updated `com.mecris.go`'s `PocketIdAuthRepository` to check the JWT `exp` claim directly on state load (`loadAuthState`), keeping the app in `AuthState.Authenticated` if the token has not actually expired, rather than immediately dropping into an error state when the local identity endpoint is transiently unreachable. Added a roam-safe silent token refresh (`refreshAccessTokenSilent`) and companion unit tests (`JwtExpParserTest.kt`).
2. **MikroTik Router Configuration Audit & Client Isolation Disabling:**
   Programmatically dumped all 18 configuration sections from the MikroTik `hAP ax^2` router (RouterOS 7.24.4) over its REST API into local backup files (protected via `.gitignore`). Analyzed bridge ports, bridge filters, firewall tables, and wireless datapaths. Explicitly forced `client-isolation=false` on WiFi datapath `capdp` (`*1`) across both `mikrotika2` (2.4 GHz) and `mikrotika5` (5 GHz) radios.
3. **Restored the Local MCP Python Environment:**
   Resolved the missing `dotenv` error by pinning [`.python-version`](../.python-version) back to `3.13` (away from `3.14`, which was failing to compile native wheels for `pydantic-core` / `pyo3`). Successfully synced `uv` and verified healthy MCP stdio communication and live Narrator context.

---

## 2. Part 1: Android Auth Roaming Resilience

### Problem
- On the **14-net**, the app authenticated and communicated with the NAS smoothly.
- On the **13-net**, TCP connections to `metnoom.urmanac.com` (`10.17.13.140:443`) timed out when initiated by the app UID, causing AppAuth token requests to throw `AuthorizationException {type:0, code:3, "Network error"}`.
- Whenever AppAuth flagged `needsTokenRefresh=true`, the app would attempt an immediate refresh. If that network call timed out, it threw an error and dropped the user out of the authenticated state completely.

### Fix Applied
- **JWT Expiry Check (`loadAuthState`)**:
  - Implemented `parseJwtExp(jwt: String): Long?` and `isAccessTokenJwtValid(jwt: String): Boolean` in `PocketIdAuthRepository.kt`.
  - When `internalAuthState.needsTokenRefresh` is true, the repository checks if the token's JWT `exp` claim is still in the future (with a 30s buffer). If valid, it immediately emits `AuthState.Authenticated(jwt)` so the user stays logged in while roaming, launching `refreshAccessTokenSilent()` in the background.
- **Roam-Safe Background Refresh (`refreshAccessTokenSilent`)**:
  - Distinguishes between permanent errors (e.g. token revocation, `invalid_grant`) and transient network dropouts. Transient failures log a warning and return `false`, preserving `_authState` so network transitions do not bounce the user out to the login screen.
- **Unit Testing**:
  - Added [JwtExpParserTest.kt](../../mecris-go-project/app/src/test/java/com/mecris/go/auth/JwtExpParserTest.kt) covering valid future tokens, expired tokens, malformed JWTs, whitespace variants, and roaming scenarios.
  - All unit tests passed (`./gradlew testDebugUnitTest`).

---

## 3. Part 2: MikroTik Router Audit & Client Isolation

### Target Device
- **Hardware**: MikroTik `hAP ax^2` (`C52iG-5HaxD2HaxD-TC`), ARM64
- **OS**: RouterOS `7.24.4 (stable)`
- **IP**: `10.17.13.249` (`bridgeLocal`), `10.17.14.249` (`ether1`)

### Procedure & Discovery
1. Authenticated via persistent session to `http://10.17.13.249/rest/`.
2. Created a comprehensive automated backup script downloading 18 configuration endpoints into `scripts/mikrotik-backup/` as timestamped JSON files.
3. Updated [`.gitignore`](../../.gitignore) to ensure `/scripts/mikrotik-backup/*.json` is ignored, protecting secrets and network topology details.
4. **Findings**:
   - Bridge ports (`ether2`–`ether5`, `mikrotika2`, `mikrotika5`) had `horizon=none` and `auto-isolate=false`.
   - `/interface/bridge/filter` was empty (no Layer 2 MAC filtering).
   - `/ip/firewall/filter` had no intra-subnet drop rules.
   - The default datapath `capdp` (`*1`) lacked an explicit `client-isolation` declaration.
5. **Applied Fix**:
   - Sent `PATCH` to `/rest/interface/wifi/datapath/*1` with `{"client-isolation": "false"}`.
   - Verified that both wireless interfaces (`mikrotika2` and `mikrotika5`) inherited `datapath.client-isolation: false`.
6. Documented the full network layout and runbook in [`scripts/mikrotik-backup/README.md`](../../scripts/mikrotik-backup/README.md).

---

## 4. Part 3: Python Environment & MCP Server Revival

### Problem
Starting the `mecris` MCP server produced:
```text
ModuleNotFoundError: No module named 'dotenv'
```
Checking `.venv/bin/python3` revealed Python `3.14.7`. Renovate had previously bumped `.python-version` to `3.14`. Under Python 3.14:
- `pydantic-core==2.33.2` failed to build wheels via `maturin` / `pyo3-ffi` (`the configured Python interpreter version (3.14) is newer than PyO3's maximum supported version (3.13)`).
- Because `uv sync` had aborted during build, `.venv` was left unpopulated without core packages like `dotenv` and `mcp`.

### Solution
1. Reverted `.python-version` to `3.13`.
2. Ran `uv sync`, successfully installing all 274 packages into `.venv`.
3. Verified stdio handshake with `mcp_server.py --stdio`.
4. Called `get_narrator_context` via the active MCP server tool, verifying:
   - ✅ Physical activity completed today (**7,805 steps / ~2.78 miles**).
   - ✅ Neon database connected.
   - ✅ Android client and Akamai functions actively reporting healthy heartbeats.
   - ⚠️ Flagged 1-day Beeminder warnings for `helix-ml` and `reviewstack` to service tomorrow.

---

## 5. Repository State & Commits

- `2f8588e`: `fix(auth): roaming resilience — use cached JWT when token endpoint unreachable`
- `1f4f4a8`: `docs(net): document mikrotik discovery, backup runbook, and wireguard WAN roadmap`
- `465de7d`: `docs(net): refine mikrotik README to focus strictly on as-is network topology and applied fixes`
- `27bcd2a`: `fix(env): pin python version to 3.13 in .python-version and sync uv venv`

---

## 5. Part 4: Local MCP Configuration Normalization

### Context & Requirements
- Prior configs contained `@modelcontextprotocol/server-github` passing through `${GITHUB_TOKEN}` / `GITHUB_PERSONAL_ACCESS_TOKEN`.
- Sharing personal access tokens into subprocess environments violates local privacy boundaries and is forbidden under vMLX harnesses.
- Standardized all local configuration files (`.mcp.json`, `.gemini/settings.json`, and `.mcp/mecris.json`) to invoke `uv run` against `/Users/yebyen/w/mecris/mcp_server.py` with `PYTHONPATH` set cleanly.

### Commit
- `97f175c`: `fix(mcp): normalize all local MCP configs and remove github server`

---

## 6. Next Steps & Morning Move Roadmap (Site-to-Site WireGuard)

### Context: The New House Move
In the morning, the MikroTik router (`10.17.13.0/24`) is moving to the new house over Comcast 1Gbit (~2 miles away). The goal is to establish a seamless, transparent Site-to-Site WireGuard tunnel connecting the **13-net** and **14-net** so devices communicate without running VPN software on individual clients.

### Operational Blueprint (Phased Plan):

#### Phase 1: Addressing & DDNS Foundations
1. **MikroTik Dynamic DNS (IP Cloud)**:
   - Enable built-in MikroTik DDNS: `/ip/cloud/set ddns-enabled=yes`.
   - Generates a permanent unique DNS name (`*.sn.mynetname.net`) resolving to the router's current public IP.
2. **14-net DDNS Endpoint**:
   - Establish dynamic DNS on the 14-net gateway or via an internal lightweight agent/container to track WAN changes.
3. **Subnet Non-Overlap Verification**:
   - Confirmed: 13-net (`10.17.13.0/24`) vs 14-net (`10.17.14.0/24`) have zero IP overlap.
4. **Comcast NAT Traversal / Bridge Mode**:
   - Put residential Comcast gateway into Bridge Mode where possible, or configure port forwarding for WireGuard UDP (e.g., port 13231) to the router's WAN interface to prevent double NAT handshake stalls.

#### Phase 2: WireGuard Tunnel Interface & Peering
1. **Transit Network**:
   - Point-to-point transit block: `10.254.1.0/30`
     - MikroTik Peer IP: `10.254.1.1/30`
     - 14-net Gateway Peer IP: `10.254.1.2/30`
2. **AllowedIPs Routing**:
   - MikroTik peer definition: `AllowedIPs=10.254.1.2/32, 10.17.14.0/24`
   - 14-net peer definition: `AllowedIPs=10.254.1.1/32, 10.17.13.0/24`

#### Phase 3: Route Orchestration & Firewall Policies
1. **Static Routing**:
   - MikroTik route: `/ip/route/add dst-address=10.17.14.0/24 gateway=wireguard-tunnel`
   - 14-net route: dst-address `10.17.13.0/24` gateway point to tunnel peer.
2. **Firewall Adjustments**:
   - In MikroTik `forward` chain, permit `in-interface=wireguard-tunnel out-interface=bridgeLocal` (and reverse).
   - Exempt inter-subnet site-to-site traffic from FastTrack if needed so established tunnel packets are not prematurely dropped or mangled.
