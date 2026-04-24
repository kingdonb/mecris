package com.mecris.go.sync

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class LogMessageRequestDtoTest {

    @Test
    fun `LogMessageRequestDto has required type and channel fields`() {
        val dto = LogMessageRequestDto(type = "arabic_pressure", channel = "android_native")
        assertEquals("arabic_pressure", dto.type)
        assertEquals("android_native", dto.channel)
        assertNull(dto.sent_at)
    }

    @Test
    fun `LogMessageRequestDto accepts sent_at ISO timestamp`() {
        val ts = "2026-04-24T12:00:00Z"
        val dto = LogMessageRequestDto(type = "walk_reminder", channel = "android_native", sent_at = ts)
        assertEquals("walk_reminder", dto.type)
        assertEquals("android_native", dto.channel)
        assertEquals(ts, dto.sent_at)
    }

    @Test
    fun `nag type mapping covers all prefKeys`() {
        val mapping = mapOf(
            "last_arabic_nag_timestamp" to "arabic_pressure",
            "last_walk_nag_timestamp" to "walk_reminder",
            "last_greek_nag_timestamp" to "greek_reminder"
        )
        for ((prefKey, expectedType) in mapping) {
            val nagType = when (prefKey) {
                "last_arabic_nag_timestamp" -> "arabic_pressure"
                "last_walk_nag_timestamp" -> "walk_reminder"
                "last_greek_nag_timestamp" -> "greek_reminder"
                else -> "unknown"
            }
            assertEquals("prefKey $prefKey should map to $expectedType", expectedType, nagType)
        }
    }

    @Test
    fun `unknown prefKey maps to unknown type`() {
        val nagType = when ("some_new_key") {
            "last_arabic_nag_timestamp" -> "arabic_pressure"
            "last_walk_nag_timestamp" -> "walk_reminder"
            "last_greek_nag_timestamp" -> "greek_reminder"
            else -> "unknown"
        }
        assertEquals("unknown", nagType)
    }
}
