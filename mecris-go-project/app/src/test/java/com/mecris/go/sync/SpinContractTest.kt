package com.mecris.go.sync

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.http.GET
import retrofit2.http.POST
import java.io.File

/**
 * Wire-format contract tests: real Spin JSON from contracts/ (read in place, never
 * copied) goes through the same Gson the app uses. Gson silently fills a missing
 * non-null Kotlin field with false/0/null, so hand-built DTOs in other tests cannot
 * catch shape drift; these can.
 */
class SpinContractTest {
    private val gson = Gson()

    private fun contract(name: String): String = File("../../contracts/$name").readText()

    @Test
    fun `heartbeat without mcp_server_active parses to null, not false`() {
        val dto = gson.fromJson(contract("spin_heartbeat_response.json"), HeartbeatResponseDto::class.java)
        assertEquals("success", dto.status)
        assertNull(
            "Spin never sends mcp_server_active; a missing field must not read as 'MCP is dark'",
            dto.mcp_server_active
        )
    }

    @Test
    fun `status response parses as SyncResponse`() {
        val dto = gson.fromJson(contract("spin_status_response.json"), SyncResponse::class.java)
        assertEquals("success", dto.status)
        assertEquals("Verification code sent", dto.message)
    }

    @Test
    fun `the phone declares no trigger-reminders or cloud-sync route (#368)`() {
        val routes = SyncServiceApi::class.java.methods.flatMap { m ->
            listOfNotNull(
                m.getAnnotation(POST::class.java)?.value,
                m.getAnnotation(GET::class.java)?.value
            )
        }
        assertTrue("routes were not read", routes.contains("heartbeat"))
        assertTrue(
            "The cloud cron owns these; the phone must not call them. Found: $routes",
            routes.none { it.startsWith("internal/trigger-reminders") || it.startsWith("internal/cloud-sync") }
        )
    }
}
