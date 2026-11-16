package com.mecris.go.sync

import android.app.NotificationManager
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.time.Instant

/**
 * #363 phase 1: the phone's request bodies against contracts/message_events.json,
 * read in place (never copied), through the same Gson the app uses.
 */
class MessageEventContractTest {
    private val gson = Gson()

    private val contract: JsonObject =
        JsonParser.parseString(File("../../contracts/message_events.json").readText()).asJsonObject

    private fun api(name: String): JsonObject = contract.getAsJsonObject("api").getAsJsonObject(name)

    private fun keys(any: Any): Set<String> = JsonParser.parseString(gson.toJson(any)).asJsonObject.keySet()

    @Test
    fun `event body matches the log_message_event request example exactly`() {
        val example = api("log_message_event").getAsJsonObject("request_example")
        val dto = MessageEventRequestDto.of(
            clientRef = example.get("client_ref").asString,
            event = example.get("event").asString,
            at = Instant.parse(example.get("at").asString)
        )
        assertEquals(example, JsonParser.parseString(gson.toJson(dto)))
    }

    @Test
    fun `phone vocabulary is the contract's`() {
        val phone = contract.getAsJsonObject("event_vocabulary").getAsJsonArray("phone").map { it.asString }.toSet()
        assertEquals(phone, NagEvents.PHONE_EVENTS)
        assertEquals(
            setOf(NagEvents.TAPPED, NagEvents.DISMISSED, NagEvents.ACTION_LATER, NagEvents.ACTION_START),
            phone
        )
    }

    @Test
    fun `contract example client_ref passes the phone's rule`() {
        val ref = api("log_message_event").getAsJsonObject("request_example").get("client_ref").asString
        assertTrue(NagEvents.isValidClientRef(ref))
    }

    @Test
    fun `log-message body with client_ref carries every field of the contract example`() {
        val example = api("log_message").getAsJsonObject("request_example")
        val dto = LogMessageRequestDto.shownNag(
            example.get("type").asString,
            Instant.parse(example.get("sent_at").asString),
            example.get("client_ref").asString
        )
        val body = JsonParser.parseString(gson.toJson(dto)).asJsonObject
        for (key in example.keySet()) {
            assertEquals("log-message field '$key'", example.get(key), body.get(key))
        }
        assertEquals("android_native", body.get("channel").asString)
    }

    @Test
    fun `log-message body without client_ref is the old shape`() {
        val dto = LogMessageRequestDto.shownNag("walk_reminder", Instant.parse("2026-11-15T19:02:11Z"))
        assertEquals(setOf("type", "channel", "sent_at"), keys(dto))
    }

    @Test
    fun `heartbeat with notifications_enabled matches the contract example`() {
        val example = api("heartbeat").getAsJsonObject("request_example")
        val dto = HeartbeatRequestDto(
            role = example.get("role").asString,
            process_id = example.get("process_id").asString,
            notifications_enabled = example.get("notifications_enabled").asBoolean
        )
        assertEquals(example, JsonParser.parseString(gson.toJson(dto)))
    }

    @Test
    fun `heartbeat without notifications_enabled omits the field`() {
        assertEquals(setOf("role", "process_id"), keys(HeartbeatRequestDto(role = "android_client", process_id = "com.mecris.go")))
    }

    @Test
    fun `notifications_enabled needs the app switch and a non-silenced nag channel`() {
        assertTrue(NagNotificationManager.notificationsEnabled(true, NotificationManager.IMPORTANCE_HIGH))
        assertTrue(NagNotificationManager.notificationsEnabled(true, NotificationManager.IMPORTANCE_LOW))
        // Channel not created yet: only the app switch is known.
        assertTrue(NagNotificationManager.notificationsEnabled(true, null))
        assertFalse(NagNotificationManager.notificationsEnabled(true, NotificationManager.IMPORTANCE_NONE))
        assertFalse(NagNotificationManager.notificationsEnabled(false, NotificationManager.IMPORTANCE_HIGH))
        assertFalse(NagNotificationManager.notificationsEnabled(false, null))
    }
}
