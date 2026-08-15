---
name: chore-pocketid-inventory
description: 'Weekend chore 5-minute survey and verification for PocketID OIDC server on Synology, DNS/LAN perimeter reachability, JWKS discovery, and AppAuth token exchange health. Trigger with /chore-pocketid-inventory'
allowed-tools: ['run_command', 'view_file', 'grep_search', 'list_dir', 'call_mcp_tool']
---

# Weekend Chore: PocketID OIDC Server Inventory

Part of the **Weekend Chores** accountability workflow. This skill guides the **human operator** and AI assistant through a 5-minute inspection of the **PocketID** OpenID Connect authentication service running locally on the home Synology NAS (`https://metnoom.urmanac.com`), ensuring passkey validation, client ID bindings, and OIDC discovery endpoints are healthy.

## The PocketID Architecture & Authentication Boundary

PocketID serves as the primary **Neural Link** identity provider across the Mecris ecosystem:
- **Server Instance**: Containerized PocketID instance running on the local Synology NAS.
- **LAN IP & Perimeter**: `10.17.13.140` / `https://metnoom.urmanac.com`.
- **Client Application ID**: `21f65a91-c4df-468d-a256-3b66a54c6d5f` (Mecris Go Android client).
- **Redirect URI**: `com.mecris.go:/oauth2redirect`.
- **Token Lifecycle**:
  - 30-day sliding window refresh token TTL.
  - Proactive background refresh at 80% of TTL.
  - Hardware-backed encrypted credential storage via `EncryptedSharedPreferences` / Android MasterKey.

---

## 5-Minute Guided Chore Routine

### Step 1: Verify LAN Reachability & DNS Resolution
```bash
# Ping the local Synology PocketID host
ping -c 3 metnoom.urmanac.com
```
- Confirms local DNS resolves `metnoom.urmanac.com` to the internal LAN IP (`10.17.13.140`) without routing drops.

### Step 2: Query OIDC Discovery Endpoints
```bash
# Query openid-configuration from PocketID
curl -s https://metnoom.urmanac.com/.well-known/openid-configuration | python3 -m json.tool
```
- Verifies HTTP 200 response and confirms valid endpoints:
  - `authorization_endpoint`: `https://metnoom.urmanac.com/authorize`
  - `token_endpoint`: `https://metnoom.urmanac.com/api/oidc/token`
  - `jwks_uri`: `https://metnoom.urmanac.com/.well-known/jwks.json`

### Step 3: Verify JWKS Public Key Certificates
```bash
# Inspect active public signing keys
curl -s https://metnoom.urmanac.com/.well-known/jwks.json | python3 -m json.tool
```
- Confirms the cryptographic signing keys are active and non-empty.

### Step 4: Verify Android Client AppAuth Error Classification
```bash
# Inspect Android PocketIdAuthRepository for structured AppAuth error handling
view_file mecris-go-project/app/src/main/java/com/mecris/go/auth/AuthError.kt
```
- Confirms `NetworkUnreachable` vs. `TokenRevoked` classifications differentiate transient network hops from true session expiry.

### Step 5: Human Visual Confirmation (The Chore)
1. Open the **PocketID Admin Console** in your browser (`https://metnoom.urmanac.com`).
2. Confirm user accounts, active passkeys, and client applications are listed with green status.
3. Check your phone to ensure the Mecris Go dashboard shows a calm, connected state.
