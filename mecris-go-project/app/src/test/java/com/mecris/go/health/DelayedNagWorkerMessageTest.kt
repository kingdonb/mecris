package com.mecris.go.health

import org.junit.Assert.assertFalse
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
}
