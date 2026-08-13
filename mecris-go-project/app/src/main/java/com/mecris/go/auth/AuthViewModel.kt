package com.mecris.go.auth

import android.app.Application
import android.content.Intent
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.viewModelScope
import kotlin.math.pow
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit

/**
 * ViewModel for authentication UI state and deep-link handling.
 * Manages:
 * - Auth state (Idle, Loading, Authenticated, Error)
 * - Deep-link routing to auth screen with pre-filled email
 * - Auto-retry with exponential backoff (max 4h) for non-permanent errors
 */
class AuthViewModel(application: Application) : AndroidViewModel(application) {

    // Repository will be injected via Hilt/Koin in production; for now we create it
    private val repository by lazy {
        PocketIdAuthRepository(
            context = getApplication()
        )
    }

    private val _authState = MutableStateFlow<AuthState>(AuthState.Idle)
    val authState: StateFlow<AuthState> = _authState

    // Deep-link email for pre-filling
    private val _deepLinkEmail = MutableLiveData<String?>()
    val deepLinkEmail: LiveData<String?> = _deepLinkEmail

    // Auto-retry state
    private var retryJob: Job? = null
    private var retryCount = 0

    companion object {
        private const val MAX_RETRY_HOURS = 4
        private const val BASE_RETRY_DELAY_MINUTES = 5L
    }

    init {
        observeRepositoryState()
    }

    private fun observeRepositoryState() {
        viewModelScope.launch {
            repository.authState.collect { state ->
                _authState.value = state

                // Handle auto-retry for transient errors
                when (state) {
                    is AuthState.Error -> {
                        if (!state.isPermanent && !repository.isExplicitlyLoggedOut()) {
                            scheduleAutoRetry()
                        } else {
                            cancelAutoRetry()
                        }
                    }
                    is AuthState.Authenticated -> {
                        cancelAutoRetry()
                        retryCount = 0
                    }
                    else -> cancelAutoRetry()
                }
            }
        }
    }

    /** Handles incoming deep-link intent for auth screen. */
    fun handleDeepLink(intent: Intent?) {
        val uri = intent?.data
        if (uri != null && uri.scheme == "mecris" && uri.host == "auth") {
            val email = uri.getQueryParameter("email")
            _deepLinkEmail.value = email

            // If we have a permanent error, trigger re-auth with pre-filled email
            val currentState = _authState.value
            if (currentState is AuthState.Error && currentState.isPermanent) {
                triggerReAuth(email)
            }
        }
    }

    /** Starts authentication flow with optional email hint. */
    fun authenticate(launcher: androidx.activity.result.ActivityResultLauncher<Intent>, emailHint: String? = null) {
        cancelAutoRetry()
        repository.authenticateWithPasskey(launcher, emailHint)
    }

    /** Triggers re-authentication (e.g., after token revocation). */
    fun triggerReAuth(emailHint: String? = null) {
        // This will be called from UI with a launcher
        // The UI should call authenticate() with the emailHint
        _deepLinkEmail.value = emailHint
    }

    /** Handles authorization response from OIDC redirect. */
    fun handleAuthResponse(intent: Intent?) {
        repository.handleAuthorizationResponse(intent)
    }

    /** Gets current access token for API calls. */
    suspend fun getAccessToken(): String? = repository.getAccessTokenSuspend()

    /** Forces immediate token refresh. */
    suspend fun forceTokenRefresh(): String? = repository.forceTokenRefresh()

    /** Explicit user logout. */
    fun signOut() {
        repository.signOut()
        cancelAutoRetry()
    }

    /** Schedules exponential backoff retry for transient errors. */
    private fun scheduleAutoRetry() {
        cancelAutoRetry()

        retryJob = viewModelScope.launch {
            while (retryCount * BASE_RETRY_DELAY_MINUTES < MAX_RETRY_HOURS * 60) {
                val delayMinutes = BASE_RETRY_DELAY_MINUTES * (2.0.pow(retryCount)).toLong()
                delay(TimeUnit.MINUTES.toMillis(delayMinutes))

                // Check if still in error state and not explicitly logged out
                val currentState = _authState.value
                if (currentState is AuthState.Error && !repository.isExplicitlyLoggedOut()) {
                    if (!currentState.isPermanent) {
                        // Trigger background refresh
                        val token = repository.forceTokenRefresh()
                        if (token != null) {
                            // Success - retry loop will exit via state observation
                            break
                        }
                    } else {
                        // Permanent error - stop retrying
                        break
                    }
                } else {
                    // No longer in error state or explicitly logged out
                    break
                }

                retryCount++
            }
        }
    }

    private fun cancelAutoRetry() {
        retryJob?.cancel()
        retryJob = null
        retryCount = 0
    }

    /** Consumes and clears the deep-link email. */
    fun consumeDeepLinkEmail(): String? {
        return _deepLinkEmail.value.also { _deepLinkEmail.value = null }
    }

    override fun onCleared() {
        super.onCleared()
        cancelAutoRetry()
        repository.dispose()
    }
}
