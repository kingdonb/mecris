package com.mecris.go.sync

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.time.ZonedDateTime

/** #395: the worker's last run, as the heartbeat reports it to the system pulse. */
class HeartbeatStatusTest {
    private val contract: JsonObject =
        JsonParser.parseString(File("../../contracts/spin_heartbeat_request.json").readText()).asJsonObject

    @Test
    fun `max chars matches the contract`() {
        assertEquals(contract.get("max_chars").asInt, HeartbeatStatus.MAX_CHARS)
    }

    @Test
    fun `cleaning follows every contract case`() {
        for (case in contract.getAsJsonArray("cases")) {
            val c = case.asJsonObject
            val body = c.getAsJsonObject("body")
            val expect = c.getAsJsonObject("expect")
            val name = c.get("name").asString
            fun raw(key: String): Any? = body.get(key)?.let { if (it.isJsonPrimitive && it.asJsonPrimitive.isString) it.asString else it.toString() }
            val isString = { key: String -> body.get(key)?.let { it.isJsonPrimitive && it.asJsonPrimitive.isString } ?: false }
            val status = if (isString("last_status")) HeartbeatStatus.clean(raw("last_status") as String) else null
            val error = if (isString("last_error")) HeartbeatStatus.clean(raw("last_error") as String) else null
            assertEquals(name, expect.get("write").asBoolean, status != null)
            if (status != null) {
                assertEquals(name, expect.get("last_status").asString, status)
                assertEquals(name, expect.get("last_error").takeIf { !it.isJsonNull }?.asString, error)
            }
        }
    }

    @Test
    fun `a run is described by its time, result and phases`() {
        val at = ZonedDateTime.parse("2026-11-17T14:05:30-05:00[America/New_York]")
        assertEquals(
            "run 14:05 ET: success (auth,hb,helix)",
            HeartbeatStatus.describe(at, "success", listOf("auth", "hb", "helix"))
        )
        assertEquals("run 14:05 ET: retry ()", HeartbeatStatus.describe(at, "retry", emptyList()))
    }

    @Test
    fun `a long phase list is cut to max chars`() {
        val at = ZonedDateTime.parse("2026-11-17T14:05:30-05:00[America/New_York]")
        val s = HeartbeatStatus.describe(at, "success", List(60) { "phase$it" })
        assertTrue(s.length <= HeartbeatStatus.MAX_CHARS)
    }

    @Test
    fun `the request DTO omits the status when there is none`() {
        val gson = Gson()
        val old = gson.toJsonTree(HeartbeatRequestDto(role = "android_client", process_id = "p")).asJsonObject
        assertNull(old.get("last_status"))
        val withStatus = gson.toJsonTree(
            HeartbeatRequestDto(role = "android_client", process_id = "p", last_status = "run 14:05 ET: success ()")
        ).asJsonObject
        assertEquals("run 14:05 ET: success ()", withStatus.get("last_status").asString)
        assertNull(withStatus.get("last_error"))
    }
}
