package com.mecris.go.ai

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SovereignBrainFallbackTest {

    @Test
    fun `arabic fallback does not contain moussaka`() {
        val fallback = SovereignBrain.goalSpecificFallback("ARABIC")
        assertFalse(
            "Arabic fallback should not mention moussaka, got: $fallback",
            fallback.contains("moussaka", ignoreCase = true)
        )
    }

    @Test
    fun `greek fallback contains moussaka`() {
        val fallback = SovereignBrain.goalSpecificFallback("GREEK")
        assertTrue(
            "Greek fallback should mention moussaka, got: $fallback",
            fallback.contains("moussaka", ignoreCase = true)
        )
    }

    @Test
    fun `walk fallback does not contain moussaka`() {
        val fallback = SovereignBrain.goalSpecificFallback("WALK")
        assertFalse(
            "Walk fallback should not mention moussaka, got: $fallback",
            fallback.contains("moussaka", ignoreCase = true)
        )
    }

    @Test
    fun `unknown goal returns generic fallback without moussaka`() {
        val fallback = SovereignBrain.goalSpecificFallback("UNKNOWN_GOAL")
        assertFalse(
            "Generic fallback should not mention moussaka, got: $fallback",
            fallback.contains("moussaka", ignoreCase = true)
        )
    }
}
