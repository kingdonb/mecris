package com.mecris.go.auth

import android.content.Context
import androidx.room.Entity
import androidx.room.PrimaryKey
import kotlinx.datetime.Clock
import kotlinx.datetime.Instant
import kotlinx.serialization.Serializable

/**
 * Exhaustive taxonomy of authentication errors.
 * No speculative cases — only errors that can be observed in production.
 */
sealed interface AuthError {
    val timestamp: Instant
    val message: String
    val isPermanent: Boolean
    val errorCode: String

    @Serializable
    data class TlsHandshakeFailed(
        override val timestamp: Instant = Clock.System.now(),
        override val message: String = "TLS handshake failed: certificate expired, hostname mismatch, or CA trust failure",
        val detail: String? = null
    ) : AuthError {
        override val isPermanent = true
        override val errorCode = "TLS_HANDSHAKE_FAILED"
    }

    @Serializable
    data class TokenRevoked(
        override val timestamp: Instant = Clock.System.now(),
        override val message: String = "Refresh token revoked: user revoked passkey in Pocket ID",
        val detail: String? = null
    ) : AuthError {
        override val isPermanent = true
        override val errorCode = "TOKEN_REVOKED"
    }

    @Serializable
    data class TokenExpired(
        override val timestamp: Instant = Clock.System.now(),
        override val message: String = "Refresh token TTL exceeded (30-day sliding window)",
        val detail: String? = null
    ) : AuthError {
        override val isPermanent = true
        override val errorCode = "TOKEN_EXPIRED"
    }

    @Serializable
    data class NoRefreshToken(
        override val timestamp: Instant = Clock.System.now(),
        override val message: String = "Session expired: no refresh token was issued",
        val detail: String? = null
    ) : AuthError {
        override val isPermanent = true
        override val errorCode = "NO_REFRESH_TOKEN"
    }

    @Serializable
    data class NetworkUnreachable(
        override val timestamp: Instant = Clock.System.now(),
        override val message: String = "Network unreachable: Tailscale tunnel down or no route to OIDC endpoint",
        val detail: String? = null
    ) : AuthError {
        override val isPermanent = false
        override val errorCode = "NETWORK_UNREACHABLE"
    }

    @Serializable
    data class OidcEndpointError(
        override val timestamp: Instant = Clock.System.now(),
        override val message: String = "OIDC endpoint returned 4xx/5xx error",
        val statusCode: Int,
        val responseBody: String? = null
    ) : AuthError {
        override val isPermanent: Boolean
            get() = statusCode >= 400 && statusCode < 500
        override val errorCode = "OIDC_ENDPOINT_ERROR"
    }

    @Serializable
    data class PasskeyValidationFailed(
        override val timestamp: Instant = Clock.System.now(),
        override val message: String = "Passkey validation failed: biometric/PIN rejected",
        val detail: String? = null
    ) : AuthError {
        override val isPermanent = false
        override val errorCode = "PASSKEY_VALIDATION_FAILED"
    }

    @Serializable
    data class Unknown(
        override val timestamp: Instant = Clock.System.now(),
        override val message: String,
        override val isPermanent: Boolean = false
    ) : AuthError {
        override val errorCode = "UNKNOWN"
    }

    companion object {
        fun fromException(e: Exception, context: Context? = null): AuthError {
            // Check AppAuth structured exception types first
            if (e is net.openid.appauth.AuthorizationException) {
                if (e.type == net.openid.appauth.AuthorizationException.TYPE_GENERAL_ERROR) {
                    if (e.code == net.openid.appauth.AuthorizationException.GeneralErrors.NETWORK_ERROR.code ||
                        e.code == net.openid.appauth.AuthorizationException.GeneralErrors.SERVER_ERROR.code
                    ) {
                        return NetworkUnreachable(detail = e.errorDescription ?: e.message ?: "AppAuth Network/Server error")
                    }
                    if (e.code == net.openid.appauth.AuthorizationException.GeneralErrors.ID_TOKEN_VALIDATION_ERROR.code) {
                        return NoRefreshToken(detail = e.errorDescription ?: e.message ?: "ID token validation failed")
                    }
                }
                if (e.type == net.openid.appauth.AuthorizationException.TYPE_OAUTH_TOKEN_ERROR) {
                    val desc = (e.errorDescription ?: e.error ?: "").lowercase()
                    if (desc.contains("invalid_grant") || desc.contains("revoked")) {
                        return TokenRevoked(detail = e.errorDescription ?: e.message)
                    }
                    if (desc.contains("expired")) {
                        return TokenExpired(detail = e.errorDescription ?: e.message)
                    }
                }
            }

            val message = e.message ?: e.javaClass.simpleName
            val lower = message.lowercase()

            return when {
                // Missing refresh token / ID token expired
                lower.contains("id token") && lower.contains("expired") ->
                    NoRefreshToken(detail = message)

                // TLS / certificate errors
                lower.contains("certificate") || lower.contains("ssl") || lower.contains("tls") ||
                lower.contains("hostname") || lower.contains("trust") || lower.contains("certpath") ->
                    TlsHandshakeFailed(detail = message)

                // Token revoked / invalid grant
                lower.contains("invalid_grant") || lower.contains("token_revoked") ||
                lower.contains("refresh token") && (lower.contains("revoked") || lower.contains("expired")) ->
                    TokenRevoked(detail = message)

                // Token expired (TTL)
                lower.contains("token_expired") || lower.contains("expired_token") ->
                    TokenExpired(detail = message)

                // Network unreachable
                lower.contains("network") || lower.contains("connection") || lower.contains("timeout") ||
                lower.contains("unreachable") || lower.contains("dns") || lower.contains("resolve") ||
                lower.contains("authorizationexception") ->
                    NetworkUnreachable(detail = message)

                // OIDC endpoint HTTP errors
                lower.contains("http") && (lower.contains("4") || lower.contains("5")) ->
                    OidcEndpointError(statusCode = extractStatusCode(message), responseBody = message)

                // Passkey / biometric
                lower.contains("biometric") || lower.contains("passkey") || lower.contains("fingerprint") ||
                lower.contains("pin") || lower.contains("credential") ->
                    PasskeyValidationFailed(detail = message)

                else -> Unknown(message = message)
            }
        }

        private fun extractStatusCode(message: String): Int {
            val pattern = """\b([45]\d{2})\b""".toRegex()
            return pattern.find(message)?.groupValues?.get(1)?.toIntOrNull() ?: 500
        }
    }
}

/**
 * Persisted error record for local Room DB telemetry.
 * Uploaded on next successful sync.
 */
@Entity(tableName = "auth_error_record")
data class AuthErrorRecord(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val errorCode: String,
    val message: String,
    val detail: String?,
    val timestamp: Long,
    val isPermanent: Boolean,
    val uploaded: Boolean = false
)

/**
 * Extension to get the human-readable detail string across all AuthError variants,
 * regardless of the underlying property name (detail vs responseBody).
 */
val AuthError.detail: String?
    get() = when (this) {
        is AuthError.TlsHandshakeFailed -> detail
        is AuthError.TokenRevoked -> detail
        is AuthError.TokenExpired -> detail
        is AuthError.NoRefreshToken -> detail
        is AuthError.NetworkUnreachable -> detail
        is AuthError.OidcEndpointError -> responseBody
        is AuthError.PasskeyValidationFailed -> detail
        is AuthError.Unknown -> null
    }

/**
 * Extension to convert AuthError to AuthErrorRecord for DB storage.
 */
fun AuthError.toRecord(): AuthErrorRecord {
    return AuthErrorRecord(
        errorCode = errorCode,
        message = message,
        detail = this.detail,
        timestamp = timestamp.toEpochMilliseconds(),
        isPermanent = isPermanent
    )
}