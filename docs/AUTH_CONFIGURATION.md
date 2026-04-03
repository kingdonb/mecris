# 🔐 Authentication Configuration (Pocket-ID & OIDC)

Mecris uses **Pocket-ID** as its OIDC (OpenID Connect) provider for user authentication and multi-tenant isolation. This document covers the configuration of Pocket-ID and how to optimize it for "submarine" operation (prolonged periods without access to the auth server).

## 1. Pocket-ID Deployment (Docker)

Pocket-ID is typically deployed via Docker Compose. Below is the standard configuration used for the Mecris environment.

```yaml
version: '3.8'
services:
  pocket-id:
    image: ghcr.io/pocket-id/pocket-id:latest
    restart: unless-stopped
    ports:
      - "1411:1411"  # Map host 1411 to container 80
    volumes:
      - "./data:/app/data"
    environment:
      - APP_URL=https://metnoom.urmanac.com
      - TRUST_PROXY=true
      - ENCRYPTION_KEY=[redacted]
      - PUID=0
      - PGID=0
    healthcheck:
      test: ["CMD", "/app/pocket-id", "healthcheck"]
      interval: 1m30s
      timeout: 5s
      retries: 2
      start_period: 10s
```

## 2. Token Lifespans & "Submarine" Operation

A common issue when using a VPN or local-only auth server is that authentication fails once the Access Token expires, even if you previously logged in successfully.

### Fixed Defaults (Pocket-ID)
As of current versions, Pocket-ID has **hardcoded** token lifespans that cannot be changed via environment variables:

- **Access Token**: 1 Hour
- **ID Token**: 1 Hour
- **Refresh Token**: 30 Days

### The "Submarine" Problem
If your session fails after exactly one hour, it means the client application (or OIDC proxy) is not correctly using the **Refresh Token**. 

- **Access Token (1h)**: Used for every request to the Spin API.
- **Refresh Token (30d)**: Used to get a *new* Access Token once the old one expires.

**Crucial Logic**: To "act as a submarine," the client must refresh the token *before* it goes underwater (disconnects from the home network/VPN). Once disconnected, the client cannot reach `metnoom.urmanac.com` to perform the refresh.

## 3. Recommended Client Configuration

To stay "underwater" for more than an hour, your OIDC client (e.g., the Android app or an OIDC proxy like OAuth2-Proxy) must be configured to:

1.  **Enable Refresh Tokens**: Ensure `offline_access` scope is requested during login.
2.  **Proactive Refresh**: Configure the client to refresh the token when it is 50-75% through its lifespan (e.g., every 30-45 minutes).
3.  **Local Caching**: The client must securely store the Refresh Token locally so it can attempt a refresh as soon as the network becomes available again.

### Root Cause Analysis (Issue #162 — Implemented)

Four compounding bugs were identified and fixed in `mecris-go-project/.../auth/PocketIdAuth.kt`:

**Bug 1 — Missing `offline_access` scope** (`PocketIdAuth.kt:67`) ✅ Fixed:
The login request did not include `offline_access`, so Pocket-ID did not issue a
durable Refresh Token. Fix applied: added `"offline_access"` to the scope list.
```kotlin
.setScopes(OPENID, PROFILE, EMAIL, "offline_access")
```

**Bug 2 — Network errors treated as permanent auth failures** (`PocketIdAuth.kt:109–112`) ✅ Fixed:
AppAuth distinguishes `invalid_grant` (real failure) from `IOException` (transient).
Fix applied: checks `ex.type == AuthorizationException.TYPE_OAUTH_TOKEN_ERROR` before
broadcasting `AuthState.Error`. Transient network errors preserve auth state silently.

**Bug 3 — Error state triggers re-auth UI** (`MainActivity.kt:1063–1074`) ✅ Fixed:
Any `AuthState.Error` used to show a "Sign In" button. Tapping it would create a new
`net.openid.appauth.AuthState()`, abandoning the still-valid Refresh Token.
Fix applied: `AuthState.Error` now carries `isPermanent: Boolean`; Sign In button is
only shown when `isPermanent == true`. Transient errors show "Network Unavailable" only.

**Bug 4 — No proactive refresh** ✅ Fixed:
`WalkHeuristicsWorker` (15-min interval) already called `getAccessTokenSuspend()` before
all network I/O. After Bug 2 fix, this call is now safe on transient network errors and
correctly acts as the proactive on-network refresh before going submarine.

Full technical report: [kingdonb/mecris#162 comment](https://github.com/kingdonb/mecris/issues/162#issuecomment-4185361982)

### Configuration Values to Consider (If/When Supported)
If future versions of Pocket-ID allow customization, these variables are the most likely candidates:
- `ACCESS_TOKEN_EXPIRATION`: Increase to 12h or 24h for longer "oxygen" during short disconnects.
- `REFRESH_TOKEN_EXPIRATION`: 30 days is usually sufficient for most accountability workflows.

## 4. Troubleshooting VPN/Network Issues

If you cannot reach the OAuth server while on VPN:
1.  Verify that `metnoom.urmanac.com` is resolvable and reachable from your VPN subnets.
2.  Check if your VPN is split-tunneling and excluding the auth server's IP.
3.  Perform a "Surface for Air" sync: Connect to the home network, open the app to trigger a token refresh, and then return to the VPN. This buys you another 60 minutes of Access Token life.
