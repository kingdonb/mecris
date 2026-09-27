package com.mecris.go.auth

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.assertFalse
import org.junit.Test
import java.time.Instant
import java.util.Base64

/**
 * Unit tests for PocketIdAuthRepository.parseJwtExp.
 *
 * Validates the "roaming resilience" path: when the app is on the 13-net and
 * can't reach the token endpoint, we use the JWT `exp` claim to decide whether
 * to stay Authenticated (exp not yet elapsed) or force a refresh (exp elapsed).
 */
class JwtExpParserTest {

    /** Builds a minimal JWT with the given exp value (no signature, no real crypto). */
    private fun makeJwt(expEpochSecs: Long): String {
        val header = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("""{"alg":"none","typ":"JWT"}""".toByteArray())
        val payload = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("""{"sub":"test","exp":$expEpochSecs}""".toByteArray())
        return "$header.$payload.fakesig"
    }

    @Test
    fun parseJwtExp_validFutureToken_returnsExpiry() {
        val expSecs = Instant.now().epochSecond + 3600 // 1 hour from now
        val jwt = makeJwt(expSecs)
        assertEquals(expSecs, PocketIdAuthRepository.parseJwtExp(jwt))
    }

    @Test
    fun parseJwtExp_validPastToken_returnsExpiry() {
        val expSecs = Instant.now().epochSecond - 100 // expired 100 seconds ago
        val jwt = makeJwt(expSecs)
        assertEquals(expSecs, PocketIdAuthRepository.parseJwtExp(jwt))
    }

    @Test
    fun parseJwtExp_notAJwt_returnsNull() {
        assertNull(PocketIdAuthRepository.parseJwtExp("not.a.jwt.with.too.many.parts"))
    }

    @Test
    fun parseJwtExp_twoPartToken_returnsNull() {
        assertNull(PocketIdAuthRepository.parseJwtExp("header.payload"))
    }

    @Test
    fun parseJwtExp_emptyString_returnsNull() {
        assertNull(PocketIdAuthRepository.parseJwtExp(""))
    }

    @Test
    fun parseJwtExp_payloadMissingExpClaim_returnsNull() {
        val header = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("""{"alg":"none"}""".toByteArray())
        val payload = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("""{"sub":"test","iat":1000000}""".toByteArray())
        val jwt = "$header.$payload.sig"
        assertNull(PocketIdAuthRepository.parseJwtExp(jwt))
    }

    @Test
    fun parseJwtExp_expWhitespaceVariants_returnsExpiry() {
        // Verify that the regex handles compact and spaced JSON equally
        val expSecs = 9999999999L
        val header = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("""{"alg":"none"}""".toByteArray())
        val payload = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("""{"sub":"test", "exp" : $expSecs}""".toByteArray())
        val jwt = "$header.$payload.sig"
        assertEquals(expSecs, PocketIdAuthRepository.parseJwtExp(jwt))
    }

    // ---- Roaming resilience: the real scenario ----

    @Test
    fun roamingScenario_tokenStillValidByExp_shouldStayAuthenticated() {
        // Simulates: phone roamed to 13-net. AppAuth says needsTokenRefresh because
        // the access token age crosses its internal threshold, but the JWT exp
        // (PocketID sets 1-day TTL) has 20 hours remaining.
        val expSecs = Instant.now().epochSecond + (20 * 3600) // 20h remaining
        val jwt = makeJwt(expSecs)
        val parsedExp = PocketIdAuthRepository.parseJwtExp(jwt)!!
        val nowSecs = Instant.now().epochSecond
        // The guard in isAccessTokenJwtValid: exp > nowSecs + 30
        assertTrue("Token with 20h remaining should be considered valid", parsedExp > nowSecs + 30)
    }

    @Test
    fun roamingScenario_tokenActuallyExpired_shouldForceRefresh() {
        // Simulates: access token is genuinely expired. Must block on refresh.
        val expSecs = Instant.now().epochSecond - 60 // expired 1 minute ago
        val jwt = makeJwt(expSecs)
        val parsedExp = PocketIdAuthRepository.parseJwtExp(jwt)!!
        val nowSecs = Instant.now().epochSecond
        assertFalse("Expired token should NOT be considered valid", parsedExp > nowSecs + 30)
    }
}
