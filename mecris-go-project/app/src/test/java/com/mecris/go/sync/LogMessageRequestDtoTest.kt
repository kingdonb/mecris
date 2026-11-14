package com.mecris.go.sync

import com.google.gson.Gson
import com.google.gson.JsonParser
import com.mecris.go.health.DelayedNagWorker
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

/** Production code behind the #213 audit row: the request body and the nag types. */
class LogMessageRequestDtoTest {

    @Test
    fun `shownNag builds an android_native row with an ISO sent_at`() {
        val dto = LogMessageRequestDto.shownNag("walk_reminder", Instant.parse("2026-11-14T20:00:00Z"))
        assertEquals("walk_reminder", dto.type)
        assertEquals("android_native", dto.channel)
        assertEquals("2026-11-14T20:00:00Z", dto.sent_at)
    }

    @Test
    fun `wire body carries type, channel and sent_at only, never message content`() {
        val json = Gson().toJson(LogMessageRequestDto.shownNag("arabic_pressure", Instant.parse("2026-11-14T20:00:00Z")))
        assertEquals(setOf("type", "channel", "sent_at"), JsonParser.parseString(json).asJsonObject.keySet())
    }

    @Test
    fun `each goal maps to its message_log type`() {
        assertEquals("arabic_pressure", DelayedNagWorker.nagTypeFor(DelayedNagWorker.GOAL_ARABIC))
        assertEquals("walk_reminder", DelayedNagWorker.nagTypeFor(DelayedNagWorker.GOAL_WALK))
        assertEquals("greek_reminder", DelayedNagWorker.nagTypeFor(DelayedNagWorker.GOAL_GREEK))
        assertEquals("unknown", DelayedNagWorker.nagTypeFor("SOMETHING_NEW"))
    }

    @Test
    fun `every type the worker can log is on Spin's allowlist`() {
        val goals = listOf(DelayedNagWorker.GOAL_ARABIC, DelayedNagWorker.GOAL_WALK, DelayedNagWorker.GOAL_GREEK)
        goals.forEach { goal ->
            assertTrue(goal, DelayedNagWorker.nagTypeFor(goal) in LogMessageRequestDto.NAG_TYPES)
        }
        assertEquals(setOf("walk_reminder", "arabic_pressure", "greek_reminder"), LogMessageRequestDto.NAG_TYPES)
    }
}
