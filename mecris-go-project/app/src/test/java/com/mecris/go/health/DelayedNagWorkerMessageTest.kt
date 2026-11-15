package com.mecris.go.health

import com.mecris.go.sync.PaceDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DelayedNagWorkerMessageTest {

    @Test
    fun `greek nag when arabic cleared does not say cards come first`() {
        val msg = DelayedNagWorker.greekNagMessage(arabicCleared = true)
        assertFalse(
            "When Arabic is cleared, nag should not imply it's still pending. Got: $msg",
            msg.contains("cards come first", ignoreCase = true)
        )
        assertTrue(
            "Greek nag should mention moussaka. Got: $msg",
            msg.contains("moussaka", ignoreCase = true)
        )
    }

    @Test
    fun `greek nag when arabic not cleared says cards come first`() {
        val msg = DelayedNagWorker.greekNagMessage(arabicCleared = false)
        assertTrue(
            "When Arabic is NOT cleared, nag should mention cards. Got: $msg",
            msg.contains("cards come first", ignoreCase = true)
        )
    }

    @Test
    fun `greek nag when arabic not cleared but arabic window closed does not say cards come first`() {
        val msg = DelayedNagWorker.greekNagMessage(arabicCleared = false, isArabicHour = false)
        assertFalse(
            "After Arabic window closes (20:00+), nag should not say 'cards come first' even if arabic not done. Got: $msg",
            msg.contains("cards come first", ignoreCase = true)
        )
        assertTrue(
            "Greek nag should still mention moussaka. Got: $msg",
            msg.contains("moussaka", ignoreCase = true)
        )
    }

    // --- #349: pace line from aggregate-status pace ---

    private val contractPace = listOf(
        PaceDto(goal = "ARABIC", remaining = 42, per_hour = 6.0, clear_by = "2026-11-14T22:00:00-05:00", due_today = 35),
        PaceDto(goal = "GREEK", remaining = 0, per_hour = 0.0, clear_by = "2026-11-14T22:00:00-05:00", due_today = 0)
    )

    @Test
    fun `pace present appends one line`() {
        assertEquals(
            "Clear the cards.\nPace: 42 reviews left today, about 6 an hour to clear them by 10:00 PM.",
            NagCopy.withPace("Clear the cards.", "ARABIC", contractPace)
        )
    }

    @Test
    fun `pace goal matches case-insensitively and rounds the hourly pace up`() {
        val pace = listOf(PaceDto(goal = "greek", remaining = 1, per_hour = 0.4, clear_by = "2026-11-14T22:00:00-05:00"))
        assertEquals(
            "Pace: 1 review left today, about 1 an hour to clear them by 10:00 PM.",
            NagCopy.paceLine("GREEK", pace)
        )
    }

    @Test
    fun `reviews left with no hourly pace (after 22 00) says due now`() {
        val pace = listOf(PaceDto(goal = "ARABIC", remaining = 12, per_hour = null, clear_by = "2026-11-14T22:00:00-05:00"))
        assertEquals("Pace: 12 reviews left today, due now.", NagCopy.paceLine("ARABIC", pace))
    }

    @Test
    fun `Spin's last hour and after 22 00 (per_hour equals remaining) says due now`() {
        // pace.rs: under an hour left, or past 22:00, per_hour == remaining.
        val lastHour = listOf(PaceDto(goal = "ARABIC", remaining = 42, per_hour = 42.0, clear_by = "2026-11-14T22:00:00-05:00"))
        assertEquals("Pace: 42 reviews left today, due now.", NagCopy.paceLine("ARABIC", lastHour))
        val oneLeft = listOf(PaceDto(goal = "GREEK", remaining = 1, per_hour = 1.0, clear_by = "2026-11-14T22:00:00-05:00"))
        assertEquals("Pace: 1 review left today, due now.", NagCopy.paceLine("GREEK", oneLeft))
        // Two hours left: still an hourly pace.
        val twoHours = listOf(PaceDto(goal = "ARABIC", remaining = 42, per_hour = 21.0, clear_by = "2026-11-14T22:00:00-05:00"))
        assertEquals("Pace: 42 reviews left today, about 21 an hour to clear them by 10:00 PM.", NagCopy.paceLine("ARABIC", twoHours))
    }

    @Test
    fun `missing clear_by assumes 10 PM`() {
        val pace = listOf(PaceDto(goal = "ARABIC", remaining = 10, per_hour = 2.0, clear_by = null))
        assertEquals("Pace: 10 reviews left today, about 2 an hour to clear them by 10:00 PM.", NagCopy.paceLine("ARABIC", pace))
    }

    @Test
    fun `pace missing or remaining 0 leaves the text unchanged`() {
        assertEquals("msg", NagCopy.withPace("msg", "ARABIC", null))
        assertEquals("msg", NagCopy.withPace("msg", "ARABIC", emptyList()))
        assertEquals("msg", NagCopy.withPace("msg", "GREEK", contractPace))
        assertEquals("msg", NagCopy.withPace("msg", "ARABIC", listOf(PaceDto(goal = "ARABIC", remaining = null))))
        assertNull(NagCopy.paceLine("GREEK", contractPace))
    }

    @Test
    fun `walk nags never get a pace line`() {
        val pace = contractPace + PaceDto(goal = "WALK", remaining = 2000, per_hour = 500.0)
        assertEquals("msg", NagCopy.withPace("msg", "WALK", pace))
    }
}
