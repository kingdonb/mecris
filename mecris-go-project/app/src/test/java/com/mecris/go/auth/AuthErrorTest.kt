package com.mecris.go.auth

import android.content.Context
import io.mockk.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class AuthErrorTest {

    private val context = mockk<Context>(relaxed = true)

    @Before
    fun setup() {}

    @After
    fun teardown() {}

    @Test
    fun `classifies TLS handshake errors`() {
        val errors = listOf(
            Exception("javax.net.ssl.SSLHandshakeException: Certificate expired"),
            Exception("SSLHandshakeException: hostname mismatch"),
            Exception("CertPathValidatorException: trust anchor not found"),
            Exception("TLS handshake failed: certificate verification failed")
        )
        
        for (e in errors) {
            val result = AuthError.fromException(e, context)
            assertTrue(result is AuthError.TlsHandshakeFailed, "Expected TlsHandshakeFailed for ${e.message}")
            assertEquals("TLS_HANDSHAKE_FAILED", result.errorCode)
            assertTrue(result.isPermanent)
        }
    }

    @Test
    fun `classifies token revoked errors`() {
        val errors = listOf(
            Exception("invalid_grant: token revoked"),
            Exception("invalid_grant: refresh token revoked by user"),
            Exception("OAuth error: invalid_grant")
        )
        
        for (e in errors) {
            val result = AuthError.fromException(e, context)
            assertTrue(result is AuthError.TokenRevoked, "Expected TokenRevoked for ${e.message}")
            assertEquals("TOKEN_REVOKED", result.errorCode)
            assertTrue(result.isPermanent)
        }
    }

    @Test
    fun `classifies token expired errors`() {
        val errors = listOf(
            Exception("token_expired: refresh token TTL exceeded"),
            Exception("expired_token: refresh token expired")
        )
        
        for (e in errors) {
            val result = AuthError.fromException(e, context)
            assertTrue(result is AuthError.TokenExpired, "Expected TokenExpired for ${e.message}")
            assertEquals("TOKEN_EXPIRED", result.errorCode)
            assertTrue(result.isPermanent)
        }
    }

    @Test
    fun `classifies network unreachable errors`() {
        val errors = listOf(
            Exception("Network unreachable: Tailscale tunnel down"),
            Exception("java.net.ConnectException: Connection refused"),
            Exception("java.net.UnknownHostException: DNS resolution failed"),
            Exception("SocketTimeoutException: connection timeout")
        )
        
        for (e in errors) {
            val result = AuthError.fromException(e, context)
            assertTrue(result is AuthError.NetworkUnreachable, "Expected NetworkUnreachable for ${e.message}")
            assertEquals("NETWORK_UNREACHABLE", result.errorCode)
            assertFalse(result.isPermanent)
        }
    }

    @Test
    fun `classifies OIDC endpoint errors`() {
        val errors = listOf(
            Exception("HTTP 400: Bad Request"),
            Exception("HTTP 401: Unauthorized"),
            Exception("HTTP 500: Internal Server Error"),
            Exception("HTTP 503: Service Unavailable")
        )
        
        for (e in errors) {
            val result = AuthError.fromException(e, context)
            assertTrue(result is AuthError.OidcEndpointError, "Expected OidcEndpointError for ${e.message}")
            assertEquals("OIDC_ENDPOINT_ERROR", result.errorCode)
            // 4xx = permanent, 5xx = transient
            val is4xx = e.message?.contains("40") == true || e.message?.contains("41") == true
            assertEquals(is4xx, result.isPermanent)
        }
    }

    @Test
    fun `classifies passkey validation errors`() {
        val errors = listOf(
            Exception("Biometric authentication failed"),
            Exception("Passkey validation rejected"),
            Exception("Fingerprint not recognized"),
            Exception("PIN entry cancelled"),
            Exception("Credential not found")
        )
        
        for (e in errors) {
            val result = AuthError.fromException(e, context)
            assertTrue(result is AuthError.PasskeyValidationFailed, "Expected PasskeyValidationFailed for ${e.message}")
            assertEquals("PASSKEY_VALIDATION_FAILED", result.errorCode)
            assertFalse(result.isPermanent)
        }
    }

    @Test
    fun `unknown errors fall back to Unknown`() {
        val error = Exception("Some completely unknown error")
        val result = AuthError.fromException(error, context)
        
        assertTrue(result is AuthError.Unknown)
        assertEquals("UNKNOWN", result.errorCode)
        assertFalse(result.isPermanent)
    }

    @Test
    fun `error record conversion preserves all fields`() {
        val error = AuthError.TokenRevoked(
            detail = "User revoked passkey in Pocket ID admin panel"
        )
        val record = error.toRecord()
        
        assertEquals("TOKEN_REVOKED", record.errorCode)
        assertEquals("Refresh token revoked: user revoked passkey in Pocket ID", record.message)
        assertEquals("User revoked passkey in Pocket ID admin panel", record.detail)
        assertTrue(record.isPermanent)
        assertFalse(record.uploaded)
        assertTrue(record.timestamp > 0)
    }
}