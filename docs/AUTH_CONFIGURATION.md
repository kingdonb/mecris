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

## 5. CLI Token Refresh (`cli/main.py`)

The Python CLI implements silent token refresh via `try_token_refresh()` before every `login` command.

### Behavior

1. Loads `~/.mecris/credentials.json` and checks for a stored `refresh_token`.
2. Decodes the current `access_token` without signature verification and checks expiry.
3. If the token is valid with **≥ 30 minutes** remaining, skips refresh entirely (avoids unnecessary round-trips to the auth server).
4. Otherwise, calls `exchange_refresh_token()` using `grant_type=refresh_token`.
5. On success: updates `credentials.json` with the new `access_token` (and rotated `refresh_token` if the server returns one).
6. On any exception (network timeout, DNS failure, HTTP 5xx): **the existing `refresh_token` is preserved**. The CLI prints a warning and falls back to the full browser PKCE flow.

### Submarine Mode Guarantee

The 30-minute pre-expiry window (`exp < now + 1800`) means the CLI will attempt a refresh before the last 30 minutes of token life. If the auth server is reachable, the access token is renewed proactively. If unreachable, the stored refresh token remains intact — no re-authentication is needed once connectivity is restored, as long as the 30-day refresh token has not expired.

```
Access token valid for ≥ 30 min → skip refresh, proceed
Access token valid for < 30 min → attempt silent refresh
  ├── server reachable → new access token stored ✅
  └── server unreachable → refresh_token preserved, falls back to browser PKCE ⚠️
```

## 6. Server-Side JWKS Verification (`services/auth_service.py`)

The MCP/Spin backend verifies incoming JWTs using one of two modes controlled by `MECRIS_MODE`.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MECRIS_MODE` | `standalone` | `standalone` = relaxed (expiry only); `cloud` = full RSA verification |
| `POCKET_ID_AUTH_ENDPOINT` | `https://metnoom.urmanac.com` | Pocket-ID base URL |
| `OIDC_JWKS_URI` | `{POCKET_ID_AUTH_ENDPOINT}/.well-known/jwks.json` | Override JWKS endpoint |
| `OIDC_ISSUER` | same as `POCKET_ID_AUTH_ENDPOINT` | Expected `iss` claim in tokens |

### Standalone Mode (`MECRIS_MODE=standalone`)

Decodes the JWT without signature verification. Only checks token expiry (`exp` claim). Use for local development where the Pocket-ID server is not accessible.

### Cloud Mode (`MECRIS_MODE=cloud`)

Full RSA signature verification via the JWKS endpoint:
1. `PyJWKClient` fetches the JWKS from `OIDC_JWKS_URI` and caches signing keys for **300 seconds** (`lifespan=300`). Keys rotate automatically every ~5 minutes.
2. Verifies the token signature against the matching key (by `kid`).
3. Validates algorithm `RS256`.
4. Checks the `iss` claim matches `OIDC_ISSUER` — mismatches return HTTP 401.

**Note**: `verify_aud=False` is intentional — Pocket-ID does not populate the `aud` claim in its JWTs.
