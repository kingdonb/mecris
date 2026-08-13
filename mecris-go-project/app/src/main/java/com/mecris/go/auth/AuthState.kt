package com.mecris.go.auth

/**
 * Represents the current state of Pocket ID authentication.
 * Consumed by ViewModels and Compose UI to drive auth-dependent behavior.
 */
sealed class AuthState {
    /** No authentication attempt has been made, or user is signed out. */
    object Idle : AuthState()

    /** Authentication or token refresh is in progress. */
    object Loading : AuthState()

    /** Successfully authenticated with a valid access token. */
    data class Authenticated(val token: String) : AuthState()

    /**
     * Authentication failed. [isPermanent] distinguishes unrecoverable errors
     * (e.g. token revoked, TLS failure) from transient ones (e.g. network unreachable)
     * that should be retried with backoff.
     */
    data class Error(val message: String, val isPermanent: Boolean = false) : AuthState()
}
