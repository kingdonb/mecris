package com.mecris.go.sync

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import com.google.gson.JsonParser
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

    // --- GET /aggregate-status?full=true (v0.3.0 shape) ---
    // Round trip: contract JSON -> DTO -> JSON (nulls kept). A field the DTO does not
    // model is dropped on the way through, so the subtree comes back missing.

    private val gsonKeepNulls = GsonBuilder().serializeNulls().create()

    private fun throughDto(json: JsonObject): JsonObject =
        gsonKeepNulls.toJsonTree(gson.fromJson(json, AggregateStatusResponseDto::class.java)).asJsonObject

    private fun fullAggregate(): JsonObject =
        JsonParser.parseString(contract("spin_aggregate_status_full.json")).asJsonObject

    @Test
    fun `aggregate full shape keeps claude_plan, pace and modalities with last_status`() {
        val raw = fullAggregate()
        val back = throughDto(raw)
        for (key in listOf("claude_plan", "pace", "modalities", "components", "goals_met", "total_goals", "all_clear", "phone_verified")) {
            assertEquals("aggregate-status field '$key' must survive the DTO", raw.get(key), back.get(key))
        }
    }

    @Test
    fun `aggregate without claude_plan, pace and last_status (today's live API) parses with nulls`() {
        val raw = fullAggregate()
        raw.remove("claude_plan")
        raw.remove("pace")
        raw.getAsJsonArray("modalities").forEach { it.asJsonObject.remove("last_status") }

        val back = throughDto(raw)
        assertEquals(JsonNull.INSTANCE, back.get("claude_plan"))
        assertEquals(JsonNull.INSTANCE, back.get("pace"))
        val modalities = back.getAsJsonArray("modalities")
        assertEquals(4, modalities.size())
        modalities.forEach { assertEquals(JsonNull.INSTANCE, it.asJsonObject.get("last_status")) }
    }

    @Test
    fun `aggregate without full=true has no modalities and still parses`() {
        val raw = fullAggregate()
        listOf("modalities", "system_pulse", "claude_plan").forEach { raw.remove(it) }

        val back = throughDto(raw)
        assertEquals(JsonNull.INSTANCE, back.get("modalities"))
        assertEquals(JsonNull.INSTANCE, back.get("claude_plan"))
        assertEquals(raw.get("pace"), back.get("pace"))
    }

    // --- GET /internal/weather-heuristic (v0.3.0: weather is not checked) ---
    // Spin's WeatherResp.temperature is Option<f64> and serialises None as null.
    // Gson leaves a primitive double at 0.0 on null, so a non-null Double would
    // show a made-up "Temp: 0.0°C" on the dashboard.

    private val v030Weather = """
        {"is_walk_appropriate": true, "conditions": "unknown", "description": "weather not checked",
         "temperature": null, "sunrise": 1763121600, "sunset": 1763158000, "is_dark": false,
         "now_epoch": 1763140000, "data_ts": 1763140000, "recommendation": "Daylight: a walk is fine. Weather is not checked."}
    """.trimIndent()

    @Test
    fun `weather with null temperature parses to null, not zero`() {
        val dto = gson.fromJson(v030Weather, WeatherHeuristicResponseDto::class.java)
        assertNull("Spin sends no temperature; it must not read as 0.0", dto.temperature)
        assertEquals("unknown", dto.conditions)
    }

    @Test
    fun `dashboard temperature line says unknown when Spin sends none`() {
        assertEquals("Temp: unknown", weatherTemperatureLine(null))
        assertEquals("Temp: 21.5°C", weatherTemperatureLine(21.5))
        assertEquals("Temp: 0.0°C", weatherTemperatureLine(0.0))
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
