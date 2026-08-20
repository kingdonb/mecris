package com.mecris.go.auth

import android.content.Context
import android.content.SharedPreferences
import android.util.Base64
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlin.coroutines.resume
import net.openid.appauth.AuthState as AppAuthAuthState
import net.openid.appauth.AuthorizationException
import net.openid.appauth.AuthorizationResponse
import net.openid.appauth.AuthorizationService
import net.openid.appauth.AuthorizationServiceConfiguration
import java.time.Duration
import java.time.Instant
import java.util.concurrent.TimeUnit

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
    var errorReporter: AuthErrorReporter? = null,
    var errorDatabase: AuthErrorDatabase? = null
) {

    // EncryptedSharedPreferences keys
    private val prefs = createEncryptedPrefs()

    // OIDC endpoints
    private val authEndpoint = "https://metnoom.urmanac.com/authorize"
    private val tokenEndpoint = "https://metnoom.urmanac.com/api/oidc/token"
    private val clientId = "21f65a91-c4df-468d-a256-3b66a54c6d5f"
    private val redirectUri = "com.mecris.go:/oauth2redirect"

    // Internal AppAuth state
    private var internalAuthState = AppAuthAuthState()

    // Mutex to prevent concurrent token refresh requests
    private val refreshMutex = Mutex()

    /** Clears transient network exception from AuthState so we can retry. */
    private fun clearTransientException() {
        val ex = internalAuthState.authorizationException
        if (ex != null) {
            val error = classifyTokenError(ex)
            if (!error.isPermanent) {
                try {
                    val jsonStr = internalAuthState.jsonSerializeString()
                    val jsonObj = org.json.JSONObject(jsonStr)
                    jsonObj.remove("authorizationException")
                    internalAuthState = AppAuthAuthState.jsonDeserialize(jsonObj.toString())
                    saveAuthState()
                } catch (e: Exception) {
                    android.util.Log.e("PocketIdAuth", "Failed to clear transient exception", e)
                }
            }
        }
    }

    // Background refresh job
    private var refreshJob: Job? = null

    // UI state flow
    private val _authState = MutableStateFlow<AuthState>(AuthState.Idle)
    val authState: StateFlow<AuthState> = _authState

    // Error events flow
    private val _errorEvents = MutableSharedFlow<AuthError>(extraBufferCapacity = 1)
    val errorEvents = _errorEvents.asSharedFlow()

    companion object {
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

        @Volatile
        private var INSTANCE: PocketIdAuthRepository? = null

        fun getInstance(
            context: Context,
            errorReporter: AuthErrorReporter? = null,
            errorDatabase: AuthErrorDatabase? = null
        ): PocketIdAuthRepository {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: PocketIdAuthRepository(
                    context.applicationContext,
                    errorReporter = errorReporter,
                    errorDatabase = errorDatabase
                ).also { INSTANCE = it }
            }.apply {
                if (errorReporter != null) this.errorReporter = errorReporter
                if (errorDatabase != null) this.errorDatabase = errorDatabase
            }
        }
    }

    init {
        loadAuthState()
        if (internalAuthState.isAuthorized && internalAuthState.refreshToken != null) {
            startBackgroundRefresh()
        }
    }

    /**
     * Creates EncryptedSharedPreferences with hardware-backed MasterKey.
     */
    private fun createEncryptedPrefs(): SharedPreferences {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        return EncryptedSharedPreferences.create(
            context,
            "auth_prefs_encrypted",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    private fun loadAuthState() {
        val json = prefs.getString(KEY_AUTH_STATE, null)
        val explicitLogout = prefs.getBoolean(KEY_EXPLICIT_LOGOUT, false)

        if (json != null && !explicitLogout) {
            try {
                internalAuthState = AppAuthAuthState.jsonDeserialize(json)
                if (internalAuthState.isAuthorized) {
                    val jwt = internalAuthState.accessToken ?: internalAuthState.idToken
                    if (jwt != null) {
                        _authState.value = AuthState.Authenticated(jwt)
                        errorReporter?.clearNotification()
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
        val now = Instant.now().toEpochMilli()
        prefs.edit()
            .putLong(KEY_REFRESH_TOKEN_ISSUED_AT, now)
            .putLong(KEY_REFRESH_TOKEN_TTL_DAYS, REFRESH_TOKEN_TTL_DAYS)
            .apply()
    }

    private fun clearAuthState() {
        prefs.edit().clear().apply()
        internalAuthState = AppAuthAuthState()
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
        val ex = AuthorizationException.fromIntent(intent)

        if (resp != null) {
            // Initialize fresh AuthState from response to clear any prior error lock
            internalAuthState = AppAuthAuthState(resp, ex)
            saveAuthState()

            // Exchange authorization code for tokens
            authService.performTokenRequest(resp.createTokenExchangeRequest()) { tokenResponse, tokenException ->
                internalAuthState.update(tokenResponse, tokenException)
                saveAuthState()

                if (tokenResponse != null) {
                    val jwt = tokenResponse.accessToken ?: tokenResponse.idToken
                    if (jwt != null) {
                        val hasRefreshToken = tokenResponse.refreshToken != null
                        android.util.Log.i(
                            "PocketIdAuth",
                            "Token exchange successful. Access token received. Refresh token present: $hasRefreshToken"
                        )
                        if (hasRefreshToken) {
                            saveRefreshTokenTimestamp()
                            startBackgroundRefresh()
                        } else {
                            android.util.Log.w(
                                "PocketIdAuth",
                                "No refresh token issued by PocketID; session will expire when access token TTL ends"
                            )
                        }
                        saveLastKnownEmail(tokenResponse.idToken?.let { parseEmailFromIdToken(it) } ?: "")
                        _authState.value = AuthState.Authenticated(jwt)
                        errorReporter?.clearNotification()
                    } else {
                        val error = AuthError.Unknown(message = "No access token received")
                        reportError(error)
                        _authState.value = AuthState.Error(error.message)
                    }
                } else {
                    val error = AuthError.fromException(tokenException ?: Exception("Unknown token exchange error"), context)
                    reportError(error)
                    _authState.value = AuthState.Error(error.message, error.isPermanent)
                }
            }
        } else {
            val error = AuthError.fromException(ex ?: Exception("Authorization failed"), context)
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
        clearTransientException()
        internalAuthState.performActionWithFreshTokens(authService) { accessToken, _, ex ->
            if (ex != null) {
                android.util.Log.e("PocketIdAuth", "performActionWithFreshTokens error: ${ex.message}", ex)
                val error = classifyTokenError(ex)
                reportError(error)
                if (error.isPermanent) {
                    _authState.value = AuthState.Error(error.message, isPermanent = true)
                } else {
                    clearTransientException()
                }
                callback(null)
            } else {
                if (accessToken != null) {
                    android.util.Log.d("PocketIdAuth", "Fresh access token retrieved successfully.")
                    saveAuthState()
                    saveRefreshTokenTimestamp()
                    _authState.value = AuthState.Authenticated(accessToken)
                    errorReporter?.clearNotification()
                }
                callback(accessToken)
            }
        }
    }

    /** Suspend version for coroutines. */
    suspend fun getAccessTokenSuspend(): String? = refreshMutex.withLock {
        return@withLock kotlinx.coroutines.suspendCancellableCoroutine { continuation ->
            getValidAccessToken { token ->
                continuation.resume(token)
            }
        }
    }

    /** Forces an immediate token refresh. */
    suspend fun forceTokenRefresh(): String? = refreshMutex.withLock {
        return@withLock kotlinx.coroutines.suspendCancellableCoroutine { continuation ->
            // Force AppAuth to treat the current access token as expired
            internalAuthState.setNeedsTokenRefresh(true)

            getValidAccessToken { token ->
                continuation.resume(token)
            }
        }
    }

    /** Classifies token refresh exceptions into AuthError taxonomy. */
    private fun classifyTokenError(ex: AuthorizationException): AuthError {
        // AppAuth doesn't expose a raw HTTP status code or a distinct "network error" type
        // constant beyond GeneralErrors.NETWORK_ERROR; delegate to the shared message-based
        // classifier used everywhere else in the auth flow for consistency.
        return AuthError.fromException(ex, context)
    }

    /** Starts background proactive token refresh at 80% TTL with exponential backoff on transient errors. */
    private fun startBackgroundRefresh() {
        stopBackgroundRefresh()

        refreshJob = scope.launch {
            var consecutiveTransientFailures = 0
            while (true) {
                val timeUntilRefresh = calculateTimeUntilProactiveRefresh()
                if (timeUntilRefresh <= 0 || consecutiveTransientFailures > 0) {
                    // Time to refresh now (or retrying after transient failure)
                    val success = refreshMutex.withLock {
                        kotlinx.coroutines.suspendCancellableCoroutine<Boolean> { continuation ->
                            refreshAccessToken { success ->
                                continuation.resume(success)
                            }
                        }
                    }
                    if (success) {
                        consecutiveTransientFailures = 0
                        // Wait a full hour before recalculating 80% TTL window
                        delay(TimeUnit.HOURS.toMillis(1))
                    } else {
                        // If error was transient, apply exponential backoff (1m, 2m, 4m, 8m... up to 30m)
                        consecutiveTransientFailures++
                        val backoffMinutes = kotlin.math.min(1L shl (consecutiveTransientFailures - 1), 30L)
                        android.util.Log.w(
                            "PocketIdAuth",
                            "Background refresh transient failure #$consecutiveTransientFailures; retrying in ${backoffMinutes}m"
                        )
                        delay(TimeUnit.MINUTES.toMillis(backoffMinutes))
                    }
                } else {
                    // Sleep until refresh time (check every hour max)
                    consecutiveTransientFailures = 0
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
        if (issuedAt == 0L) {
            saveRefreshTokenTimestamp()
            val ttlDays = prefs.getLong(KEY_REFRESH_TOKEN_TTL_DAYS, REFRESH_TOKEN_TTL_DAYS)
            val ttlMillis = Duration.ofDays(ttlDays).toMillis()
            return (ttlMillis * PROACTIVE_REFRESH_THRESHOLD_PERCENT).toLong()
        }

        val ttlDays = prefs.getLong(KEY_REFRESH_TOKEN_TTL_DAYS, REFRESH_TOKEN_TTL_DAYS)
        val ttlMillis = Duration.ofDays(ttlDays).toMillis()
        val proactiveThresholdMillis = (ttlMillis * PROACTIVE_REFRESH_THRESHOLD_PERCENT).toLong()
        val now = Instant.now().toEpochMilli()
        val proactiveTime = issuedAt + proactiveThresholdMillis

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
        errorReporter?.report(error, email)
        _errorEvents.tryEmit(error)

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
