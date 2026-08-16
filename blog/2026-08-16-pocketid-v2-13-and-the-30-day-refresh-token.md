# The Anatomy of a Mobile OIDC Edge Case: PocketID v2.13 & The 30-Day Refresh Token

**Date:** 2026-08-16  
**Author:** Antigravity (Gemini 3.7) & Kingdon  
**Topic:** OIDC Authentication, Mobile Offline Mode, AppAuth Token Lifecycles, and PocketID v2.13 Upgrade  

---

## 1. The Field Test: Outside the Home Perimeter

Following the Saturday soak of `v0.0.1-rc.6`, we took the Mecris Go Android app into the wild to test real-world offline degradation:
1. **Network Disconnect**: We walked outside the home Wi-Fi and Tailscale perimeter where our local Synology NAS-hosted PocketID instance (`https://metnoom.urmanac.com`) resides.
2. **Offline Execution**: We opened the app, watched network requests gracefully time out, and observed the calm offline UI indicator.
3. **The Return Home**: Upon returning to the home network, we expected the app to quietly resume sync. Instead, the UI presented a modal snackbar and system alert:
   > `TOKEN_EXPIRED: Refresh token TTL exceeded (30-day sliding window)`

Considering we had only authenticated 24 hours prior, requiring a re-auth after a single day contradicted our 30-day sliding window token design.

---

## 2. ADB Logcat Forensics: The 300ms Synchronous Clue

We connected ADB to inspect the system logs (`adb logcat -b all -d` and `dumpsys notification`):

```
08-16 15:33:31.136 I wm_resume_activity: com.mecris.go/.MainActivity
08-16 15:33:31.433 I notification_enqueue: [com.mecris.go, 41001, Notification(channel=mecris_auth_errors, text=TOKEN_EXPIRED: Refresh token TTL exceeded...)]
```

The error occurred in **less than 300 milliseconds** after resuming the activity.

This timing proved that AppAuth **never even attempted a network request** to PocketID when returning home. Tracing through AppAuth's internal `performActionWithFreshTokens` revealed the exact branch:

```java
if (mNeedsTokenRefresh) {
    if (mRefreshToken == null) {
        action.execute(null, null, AuthorizationException.GeneralErrors.ID_TOKEN_VALIDATION_ERROR);
        return;
    }
}
```

When the short-lived access token expired, AppAuth checked `internalAuthState.refreshToken`. Because `refreshToken` was `null`, AppAuth immediately threw a local error without reaching the network. `AuthError.fromException` matched the error string `"ID token expired"`, mapped it to `AuthError.TokenExpired` (`isPermanent = true`), and escalated the alert.

---

## 3. The Server Investigation: PocketID v2.4.0 vs v2.13.0

Why was `refreshToken` null despite the Android app requesting `offline_access`?

We queried the live PocketID OIDC configuration endpoint (`curl -s https://metnoom.urmanac.com/.well-known/openid-configuration`):
```json
{
  "scopes_supported": ["openid", "profile", "email", "groups"],
  "grant_types_supported": ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:device_code", "client_credentials"]
}
```

### The OIDC Gap in v2.4.0:
- PocketID was running **v2.4.0**.
- In v2.4.0, PocketID did not advertise `offline_access` in its discovery document and silently dropped the scope during authorization code exchange for public clients, issuing only a 1-hour access token and ID token.
- PocketID subsequently achieved official **OpenID Connect Certification™** in **v2.10.0+**, completely overhauling token lifecycle management, RFC 9068 compliance, and scope negotiation.

### Upgrading to PocketID v2.13.0:
We upgraded the container on the Synology NAS to **v2.13.0**. Querying the new discovery endpoint immediately confirmed full OIDC compliance:
```json
{
  "scopes_supported": [
    "openid",
    "profile",
    "email",
    "groups",
    "offline_access"
  ]
}
```

In the PocketID v2.13.0 Admin Console, client settings now explicitly configure:
- **Access Token Lifetime**: 1 day (default)
- **Refresh Token Lifetime**: 30 days (sliding window)

---

## 4. Android Client Hardening & Taxonomy Refinements

To ensure accurate telemetry and prevent transient or missing tokens from masquerading as 30-day window expirations, we made three key improvements:

1. **`AuthError.NoRefreshToken` Taxonomy Variant**:
   Added a dedicated, permanent error variant to `AuthError.kt`:
   ```kotlin
   @Serializable
   data class NoRefreshToken(
       override val timestamp: Instant = Clock.System.now(),
       override val message: String = "Session expired: no refresh token was issued",
       val detail: String? = null
   ) : AuthError {
       override val isPermanent = true
       override val errorCode = "NO_REFRESH_TOKEN"
   }
   ```
2. **Structured Exception Mapping**:
   Refined `AuthError.fromException` to map `GeneralErrors.ID_TOKEN_VALIDATION_ERROR` and `"id token expired"` specifically to `NoRefreshToken`.
3. **Refresh Token Presence Verification**:
   Updated `PocketIdAuthRepository.kt` to explicitly log `tokenResponse.refreshToken != null` on exchange and gate background refresh workers so they only cycle when a real refresh token is present in the hardware-encrypted keystore.
4. **Unit Test Suite**:
   Created `AuthErrorTest.kt` covering all error variants and AppAuth error codes (100% green).

---

## 5. Ready for v0.0.1 General Availability

With PocketID v2.13.0 live, `offline_access` verified, and Android auth error classification hardened, the Mecris ecosystem is primed for `v0.0.1` General Availability.
