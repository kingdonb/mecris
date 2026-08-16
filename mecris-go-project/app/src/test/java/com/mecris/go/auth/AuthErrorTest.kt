package com.mecris.go.auth

import net.openid.appauth.AuthorizationException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AuthErrorTest {

    @Test
    fun fromException_networkError_returnsNetworkUnreachable() {
        val ex = AuthorizationException.GeneralErrors.NETWORK_ERROR
        val result = AuthError.fromException(ex)

        assertTrue(result is AuthError.NetworkUnreachable)
        assertFalse(result.isPermanent)
        assertEquals("NETWORK_UNREACHABLE", result.errorCode)
    }

    @Test
    fun fromException_serverError_returnsNetworkUnreachable() {
        val ex = AuthorizationException.GeneralErrors.SERVER_ERROR
        val result = AuthError.fromException(ex)

        assertTrue(result is AuthError.NetworkUnreachable)
        assertFalse(result.isPermanent)
        assertEquals("NETWORK_UNREACHABLE", result.errorCode)
    }

    @Test
    fun fromException_idTokenValidation_returnsNoRefreshToken() {
        val ex = AuthorizationException.GeneralErrors.ID_TOKEN_VALIDATION_ERROR
        val result = AuthError.fromException(ex)

        assertTrue(result is AuthError.NoRefreshToken)
        assertTrue(result.isPermanent)
        assertEquals("NO_REFRESH_TOKEN", result.errorCode)
    }

    @Test
    fun fromException_idTokenExpiredString_returnsNoRefreshToken() {
        val ex = Exception("General error: ID token expired")
        val result = AuthError.fromException(ex)

        assertTrue(result is AuthError.NoRefreshToken)
        assertTrue(result.isPermanent)
        assertEquals("NO_REFRESH_TOKEN", result.errorCode)
        assertEquals("Session expired: no refresh token was issued", result.message)
    }

    @Test
    fun fromException_oauthInvalidGrant_returnsTokenRevoked() {
        val ex = AuthorizationException.TokenRequestErrors.INVALID_GRANT
        val result = AuthError.fromException(ex)

        assertTrue(result is AuthError.TokenRevoked)
        assertTrue(result.isPermanent)
        assertEquals("TOKEN_REVOKED", result.errorCode)
    }

    @Test
    fun fromException_tlsError_returnsTlsHandshakeFailed() {
        val ex = Exception("SSLHandshakeException: Certificate expired")
        val result = AuthError.fromException(ex)

        assertTrue(result is AuthError.TlsHandshakeFailed)
        assertTrue(result.isPermanent)
        assertEquals("TLS_HANDSHAKE_FAILED", result.errorCode)
    }

    @Test
    fun fromException_unknownException_returnsUnknown() {
        val ex = Exception("Something weird happened")
        val result = AuthError.fromException(ex)

        assertTrue(result is AuthError.Unknown)
        assertFalse(result.isPermanent)
        assertEquals("UNKNOWN", result.errorCode)
    }
}
