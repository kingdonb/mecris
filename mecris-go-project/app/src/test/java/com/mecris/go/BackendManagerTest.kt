package com.mecris.go

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BackendManagerTest {
    private val akamai = BackendManager.ENDPOINTS.first { it.first == "Akamai Cloud" }.second
    private val RETIRED_FERMYON = "https://mecris-sync-v2-glo0zpfm.fermyon.app/"

    @Test
    fun `fresh install defaults to Akamai, not the LAN Spin`() {
        assertEquals(akamai, BackendManager.resolveBaseUrl(null))
    }

    @Test
    fun `picker drops the deprovisioned Fermyon entry`() {
        assertTrue(
            BackendManager.ENDPOINTS.toString(),
            BackendManager.ENDPOINTS.none { (name, url) -> name.contains("Fermyon", true) || url.contains("fermyon", true) }
        )
    }

    @Test
    fun `picker keeps the local Python backend`() {
        assertTrue(BackendManager.ENDPOINTS.any { it.first == "Local (Python: 8080)" })
    }

    @Test
    fun `a stored Fermyon URL falls back to Akamai`() {
        assertEquals(akamai, BackendManager.resolveBaseUrl(RETIRED_FERMYON))
    }

    @Test
    fun `any other stored choice is kept`() {
        val lan = BackendManager.ENDPOINTS.first { it.first == "Local (LAN: 10.17.14.155)" }.second
        assertEquals(lan, BackendManager.resolveBaseUrl(lan))
        assertEquals("http://custom.example:3000/", BackendManager.resolveBaseUrl("http://custom.example:3000/"))
    }
}
