package com.mecris.go.health

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

/** #363 phase 1: LATER snoozes walk nags 90 minutes; START ends them for the New York day. */
class WalkSuppressionTest {

    @Test
    fun `LATER snoozes for 90 minutes`() {
        val now = Instant.parse("2026-11-15T19:05:40Z")
        assertEquals(Instant.parse("2026-11-15T20:35:40Z"), WalkSuppression.laterUntil(now))
    }

    @Test
    fun `START lasts until the next New York midnight (EST)`() {
        // 14:05 EST on Nov 15 -> midnight EST = 05:00Z on Nov 16
        assertEquals(
            Instant.parse("2026-11-16T05:00:00Z"),
            WalkSuppression.endOfNewYorkDay(Instant.parse("2026-11-15T19:05:40Z"))
        )
    }

    @Test
    fun `START late in the evening is the New York day, not the UTC day`() {
        // 23:30 EST on Nov 15 is already Nov 16 in UTC; the day still ends at 05:00Z Nov 16
        assertEquals(
            Instant.parse("2026-11-16T05:00:00Z"),
            WalkSuppression.endOfNewYorkDay(Instant.parse("2026-11-16T04:30:00Z"))
        )
    }

    @Test
    fun `START in summer uses EDT`() {
        // 10:00 EDT on Jul 4 -> midnight EDT = 04:00Z on Jul 5
        assertEquals(
            Instant.parse("2026-07-05T04:00:00Z"),
            WalkSuppression.endOfNewYorkDay(Instant.parse("2026-07-04T14:00:00Z"))
        )
    }

    @Test
    fun `START on a DST change day ends at the true next midnight`() {
        // 2026-03-08 springs forward; 12:00 EDT -> next midnight is 04:00Z Mar 9
        assertEquals(
            Instant.parse("2026-03-09T04:00:00Z"),
            WalkSuppression.endOfNewYorkDay(Instant.parse("2026-03-08T16:00:00Z"))
        )
    }

    @Test
    fun `suppressed strictly before the until time`() {
        assertTrue(WalkSuppression.isSuppressed(untilMs = 2_000L, nowMs = 1_999L))
        assertFalse(WalkSuppression.isSuppressed(untilMs = 2_000L, nowMs = 2_000L))
        assertFalse(WalkSuppression.isSuppressed(untilMs = 0L, nowMs = 1_000L))
    }

    @Test
    fun `a LATER after START never shortens the suppression`() {
        val endOfDay = 10_000L
        val later = 5_000L
        assertEquals(endOfDay, WalkSuppression.merge(currentUntilMs = endOfDay, newUntilMs = later))
        assertEquals(endOfDay, WalkSuppression.merge(currentUntilMs = later, newUntilMs = endOfDay))
    }
}
