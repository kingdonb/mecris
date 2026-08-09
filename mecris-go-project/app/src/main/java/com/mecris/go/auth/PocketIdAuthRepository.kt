package com.mecris.go.auth

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import net.openid.appauth.AuthState
import net.openid.appauth.AuthorizationException
import net.openid.appauth.AuthorizationResponse
import net.openid.appauth.AuthorizationService
import net.openid.appauth.AuthorizationServiceConfiguration
import net.openid.appauth.TokenResponse
import java.security.KeyStore
import java.security.SecureRandom
import java.time.Duration
import java.time.Instant
import java.util.concurrent.TimeUnit
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Repository for Pocket ID authentication.
 * - Stores tokens in EncryptedSharedPreferences (hardware-backed keystore)
 * - Implements 30-day sliding window refresh token TTL
 * - Background proactive refresh at 80% TTL
 * - Error classification via AuthError taxonomy
 */
class PocketIdAuthRepository(
    private val context: Context,
    private val authService: AuthorizationService = AuthorizationService(context),
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
    private val errorReporter: AuthErrorReporter? = null,
    private val lifecycleOwner: androidx.lifecycle.LifecycleOwner? = null,
    private val snackbarAnchorView: android.view.View? = null,
    private val errorDatabase: AuthErrorDatabase? = null
) {

    // EncryptedSharedPreferences keys
    private val prefs = createEncryptedPrefs()
    
    // OIDC endpoints
    private val authEndpoint = "https://metnoom.urmanac.com/authorize"
    private val tokenEndpoint = "https://metnoom.urmanac.com/api/oidc/token"
    private val clientId = "21f65a91-c4df-468d-a256-3b66a54c6d5f"
    private val redirectUri = "com.mecris.go:/oauth2redirect"
    
    // Prefs keys
    private const val KEY_AUTH_STATE = "auth_state_json"
    private const val KEY_REFRESH_TOKEN_ISSUED_AT = "refresh_token_issued_at"
    private const val KEY_REFRESH_TOKEN_TTL_DAYS = "refresh_token_ttl_days"
    private const val KEY_LAST_KNOWN_EMAIL = "last_known_email"
    private const val KEY_EXPLICIT_LOGOUT = "explicit_logout"
    
    // 30-day sliding window for refresh token
    private const val REFRESH_TOKEN_TTL_DAYS = 30L
    // Proactive refresh at 80% TTL (24 days)
    private const val PROACTIVE_REFRESH_THRESHOLD_PERCENT = 0.8
    
    // Internal AppAuth state
    private var internalAuthState = AuthState()
    
    // Background refresh job
    private var refreshJob: Job? = null
    
    // UI state flow
    private val _authState = MutableStateFlow<AuthState>(AuthState.Idle)
    val authState: StateFlow<AuthState> = _authState

    init {
        loadAuthState()
        if (internalAuthState.isAuthorized) {
            startBackgroundRefresh()
        }
    }

    /**
     * Creates EncryptedSharedPreferences with hardware-backed MasterKey.
     * Falls back to AES256_GCM if hardware keystore unavailable.
     */
    private fun createEncryptedPrefs(): androidx.security.crypto.EncryptedSharedPreferences {
        val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
        return EncryptedSharedPreferences.create(
            "auth_prefs_encrypted",
            masterKeyAlias,
            context,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    private fun loadAuthState() {
        val json = prefs.getString(KEY_AUTH_STATE, null)
        val issuedAt = prefs.getLong(KEY_REFRESH_TOKEN_ISSUED_AT, 0L)
        val explicitLogout = prefs.getBoolean(KEY_EXPLICIT_LOGOUT, false)
        
        if (json != null && !explicitLogout) {
            try {
                internalAuthState = AuthState.jsonDeserialize(json)
                if (internalAuthState.isAuthorized) {
                    val jwt = internalAuthState.accessToken ?: internalAuthState.idToken
                    if (jwt != null) {
                        _authState.value = AuthState.Authenticated(jwt)
                    } else {
                        // Has refresh token but no access token — trigger silent refresh
                        refreshAccessToken { _ -> }
                    }
                }
            } catch (e: Exception) {
                // Corrupted state — treat as logged out
                clearAuthState()
            }
        } else if (explicitLogout) {
            _authState.value = AuthState.Idle
        }
    }

    private fun saveAuthState() {
        prefs.edit()
            .putString(KEY_AUTH_STATE, internalAuthState.jsonSerializeString())
            .apply()
    }

    private fun saveRefreshTokenTimestamp() {
        val now = Instant.now().epochSecond
        prefs.edit()
            .putLong(KEY_REFRESH_TOKEN_ISSUED_AT, now)
            .putLong(KEY_REFRESH_TOKEN_TTL_DAYS, REFRESH_TOKEN_TTL_DAYS)
            .apply()
    }

    private fun clearAuthState() {
        prefs.edit().clear().apply()
        internalAuthState = AuthState()
        _authState.value = AuthState.Idle
        stopBackgroundRefresh()
    }

    fun getLastKnownEmail(): String? {
        return prefs.getString(KEY_LAST_KNOWN_EMAIL, null)
    }

    private fun saveLastKnownEmail(email: String) {
        prefs.edit().putString(KEY_LAST_KNOWN_EMAIL, email).apply()
    }

    fun isExplicitlyLoggedOut(): Boolean {
        return prefs.getBoolean(KEY_EXPLICIT_LOGOUT, false)
    }

    /** Starts the OIDC authorization flow with passkey. */
    fun authenticateWithPasskey(
        launcher: androidx.activity.result.ActivityResultLauncher<android.content.Intent>,
        emailHint: String? = null
    ) {
        _authState.value = AuthState.Loading
        
        // Clear explicit logout flag on new auth attempt
        prefs.edit().putBoolean(KEY_EXPLICIT_LOGOUT, false).apply()

        val serviceConfig = AuthorizationServiceConfiguration(
            android.net.Uri.parse(authEndpoint),
            android.net.Uri.parse(tokenEndpoint)
        )
        
        val authRequestBuilder = net.openid.appauth.AuthorizationRequest.Builder(
            serviceConfig,
            clientId,
            net.openid.appauth.ResponseTypeValues.CODE,
            android.net.Uri.parse(redirectUri)
        ).setScopes(
            net.openid.appauth.AuthorizationRequest.Scope.OPENID,
            net.openid.appauth.AuthorizationRequest.Scope.PROFILE,
            net.openid.appauth.AuthorizationRequest.Scope.EMAIL,
            "offline_access"
        )
        
        // Add login_hint if provided (for re-auth after revocation)
        emailHint?.let { authRequestBuilder.setLoginHint(it) }

        val authRequest = authRequestBuilder.build()
        val authIntent = authService.getAuthorizationRequestIntent(authRequest)
        launcher.launch(authIntent)
    }

    /** Handles the authorization response from the OIDC redirect. */
    fun handleAuthorizationResponse(intent: android.content.Intent?) {
        if (intent == null) {
            _authState.value = AuthState.Error("Authorization canceled", isPermanent = false)
            return
        }

        val resp = AuthorizationResponse.fromIntent(intent)
        val ex = net.openid.appauth.AuthorizationException.fromIntent(intent)

        internalAuthState.update(resp, ex)
        saveAuthState()

        if (resp != null) {
            // Exchange authorization code for tokens
            authService.performTokenRequest(resp.createTokenExchangeRequest()) { tokenResponse, tokenException ->
                internalAuthState.update(tokenResponse, tokenException)
                saveAuthState()
                
                if (tokenResponse != null) {
                    val jwt = tokenResponse.accessToken ?: tokenResponse.idToken
                    if (jwt != null) {
                        saveRefreshTokenTimestamp()
                        saveLastKnownEmail(tokenResponse.idToken?.let { parseEmailFromIdToken(it) } ?: "")
                        _authState.value = AuthState.Authenticated(jwt)
                        startBackgroundRefresh()
                    } else {
                        reportError(AuthError.Unknown(message = "No access token received"))
                        _authState.value = AuthState.Error("No access token received")
                    }
                } else {
                    val error = AuthError.fromException(tokenException!!, context)
                    reportError(error)
                    _authState.value = AuthState.Error(error.message, error.isPermanent)
                }
            }
        } else {
            val error = AuthError.fromException(ex!!, context)
            reportError(error)
            _authState.value = AuthState.Error(error.message, error.isPermanent)
        }
    }

    /** Parses email from ID token JWT (simple base64 decode, no verification needed for display). */
    private fun parseEmailFromIdToken(idToken: String): String? {
        return try {
            val parts = idToken.split(".")
            if (parts.size == 3) {
                val payload = parts[1]
                val padded = payload.padEnd(payload.length + (4 - payload.length % 4) % 4, '=')
                val decoded = Base64.decode(padded, Base64.URL_SAFE or Base64.NO_WRAP)
                val json = String(decoded)
                // Simple extraction without full JSON parsing
                val emailPattern = """"email"\s*:\s*"([^"]+)"""".toRegex()
                emailPattern.find(json)?.groupValues?.get(1)
            } else null
        } catch (e: Exception) {
            null
        }
    }

    /** Gets a valid access token, refreshing if necessary. */
    fun getValidAccessToken(callback: (String?) -> Unit) {
        internalAuthState.performActionWithFreshTokens(authService) { accessToken, _, ex ->
            if (ex != null) {
                val error = classifyTokenError(ex)
                reportError(error)
                if (error.isPermanent) {
                    _authState.value = AuthState.Error(error.message, isPermanent = true)
                }
                callback(null)
            } else {
                if (accessToken != null) {
                    saveAuthState()
                    _authState.value = AuthState.Authenticated(accessToken)
                }
                callback(accessToken)
            }
        }
    }

    /** Suspend version for coroutines. */
    suspend fun getAccessTokenSuspend(): String? {
        return kotlinx.coroutines.suspendCancellableCoroutine { continuation ->
            getValidAccessToken { token ->
                continuation.resume(token)
            }
        }
    }

    /** Forces an immediate token refresh. */
    suspend fun forceTokenRefresh(): String? {
        return kotlinx.coroutines.suspendCancellableCoroutine { continuation ->
            // Invalidate current access token to force refresh
            internalAuthState.accessToken = null
            internalAuthState.accessTokenExpirationTime = 0
            saveAuthState()
            
            getValidAccessToken { token ->
                continuation.resume(token)
            }
        }
    }

    /** Classifies token refresh exceptions into AuthError taxonomy. */
    private fun classifyTokenError(ex: AuthorizationException): AuthError {
        val message = ex.message ?: ""
        val lower = message.lowercase()
        
        return when {
            ex.type == AuthorizationException.TYPE_OAUTH_TOKEN_ERROR && 
            (lower.contains("invalid_grant") || lower.contains("revoked")) ->
                AuthError.TokenRevoked(detail = message)
            ex.type == AuthorizationException.TYPE_OAUTH_TOKEN_ERROR && 
            lower.contains("expired") ->
                AuthError.TokenExpired(detail = message)
            ex.type == AuthorizationException.TYPE_NETWORK_ERROR ->
                AuthError.NetworkUnreachable(detail = message)
            ex.type == AuthorizationException.TYPE_HTTP_ERROR ->
                AuthError.OidcEndpointError(statusCode = ex.responseCode, responseBody = message)
            else -> AuthError.Unknown(message = message, isPermanent = ex.type != AuthorizationException.TYPE_NETWORK_ERROR)
        }
    }

    /** Starts background proactive token refresh at 80% TTL. */
    private fun startBackgroundRefresh() {
        stopBackgroundRefresh()
        
        refreshJob = scope.launch {
            while (true) {
                val timeUntilRefresh = calculateTimeUntilProactiveRefresh()
                if (timeUntilRefresh <= 0) {
                    // Time to refresh now
                    refreshAccessToken { success ->
                        if (!success) {
                            // Error already reported via callback
                        }
                    }
                    // Wait a bit before recalculating
                    delay(1, TimeUnit.HOURS)
                } else {
                    // Sleep until refresh time (check every hour max)
                    val sleepTime = kotlin.math.min(timeUntilRefresh, TimeUnit.HOURS.toMillis(1))
                    delay(sleepTime)
                }
            }
        }
    }

    private fun stopBackgroundRefresh() {
        refreshJob?.cancel()
        refreshJob = null
    }

    /** Calculates milliseconds until proactive refresh (80% of TTL). */
    private fun calculateTimeUntilProactiveRefresh(): Long {
        val issuedAt = prefs.getLong(KEY_REFRESH_TOKEN_ISSUED_AT, 0L)
        if (issuedAt == 0L) return 0 // No timestamp, refresh immediately
        
        val ttlDays = prefs.getLong(KEY_REFRESH_TOKEN_TTL_DAYS, REFRESH_TOKEN_TTL_DAYS)
        val ttlMillis = Duration.ofDays(ttlDays).toMillis()
        val proactiveThresholdMillis = (ttlMillis * PROACTIVE_REFRESH_THRESHOLD_PERCENT).toLong()
        val now = Instant.now().epochSecond * 1000
        val expiry = issuedAt * 1000 + ttlMillis
        val proactiveTime = issuedAt * 1000 + proactiveThresholdMillis
        
        return proactiveTime - now
    }

    /** Performs access token refresh, returns success. */
    private fun refreshAccessToken(callback: (Boolean) -> Unit) {
        internalAuthState.performActionWithFreshTokens(authService) { accessToken, _, ex ->
            if (ex != null) {
                val error = classifyTokenError(ex)
                reportError(error)
                if (error.isPermanent) {
                    _authState.value = AuthState.Error(error.message, isPermanent = true)
                    stopBackgroundRefresh()
                }
                callback(false)
            } else {
                if (accessToken != null) {
                    saveAuthState()
                    saveRefreshTokenTimestamp() // Sliding window: update timestamp on successful refresh
                    _authState.value = AuthState.Authenticated(accessToken)
                }
                callback(accessToken != null)
            }
        }
    }

    /** Explicit user logout — clears everything and sets explicit logout flag. */
    fun signOut() {
        clearAuthState()
        prefs.edit().putBoolean(KEY_EXPLICIT_LOGOUT, true).apply()
        errorReporter?.clearNotification()
    }

    /** Reports error via AuthErrorReporter if available. */
    private fun reportError(error: AuthError) {
        val email = getLastKnownEmail()
        errorReporter?.report(error, email, lifecycleOwner, snackbarAnchorView)
        
        // Persist to Room DB for telemetry upload on next sync
        errorDatabase?.let { db ->
            scope.launch(Dispatchers.IO) {
                db.authErrorDao().insert(error.toRecord())
            }
        }
    }

    fun dispose() {
        stopBackgroundRefresh()
        authService.dispose()
    }
}

sealed class AuthState {
    object Idle : AuthState()
    object Loading : AuthState()
    data class Authenticated(val jwt: String) : AuthState()
    data class Error(val message: String, val isPermanent: Boolean = true) : AuthState()
}