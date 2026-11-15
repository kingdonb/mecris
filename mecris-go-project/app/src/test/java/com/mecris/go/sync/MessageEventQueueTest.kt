package com.mecris.go.sync

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

/** #363 phase 1: the durable event queue behind POST /internal/log-message-event. */
class MessageEventQueueTest {

    private class MemoryStore : MessageEventQueue.Store {
        var json: String? = null
        override fun read(): String? = json
        override fun write(json: String) { this.json = json }
    }

    private fun event(n: Int, kind: String = NagEvents.TAPPED) =
        MessageEventRequestDto(client_ref = "ref-$n", event = kind, at = "2026-11-15T19:0$n:00Z")

    @Test
    fun `enqueued events persist through the store`() {
        val store = MemoryStore()
        MessageEventQueue(store).enqueue(event(1))
        MessageEventQueue(store).enqueue(event(2, NagEvents.DISMISSED))

        assertEquals(listOf(event(1), event(2, NagEvents.DISMISSED)), MessageEventQueue(store).pending())
    }

    @Test
    fun `queue is capped and drops the oldest`() {
        val queue = MessageEventQueue(MemoryStore(), cap = 3)
        (1..5).forEach { queue.enqueue(event(it)) }
        assertEquals(listOf(event(3), event(4), event(5)), queue.pending())
    }

    @Test
    fun `default cap is 200`() {
        val queue = MessageEventQueue(MemoryStore())
        (1..250).forEach { queue.enqueue(MessageEventRequestDto("ref-$it", NagEvents.TAPPED, "2026-11-15T19:00:00Z")) }
        assertEquals(200, queue.pending().size)
        assertEquals("ref-51", queue.pending().first().client_ref)
    }

    @Test
    fun `a corrupt store reads as empty`() {
        val store = MemoryStore().apply { json = "{not json" }
        assertEquals(emptyList<MessageEventRequestDto>(), MessageEventQueue(store).pending())
    }

    @Test
    fun `200, 201 and 404 drop the event`() = runBlocking {
        for (code in listOf(200, 201, 404)) {
            val queue = MessageEventQueue(MemoryStore())
            queue.enqueue(event(1))
            val retry = queue.drain { code }
            assertFalse("HTTP $code", retry)
            assertEquals("HTTP $code", emptyList<MessageEventRequestDto>(), queue.pending())
        }
    }

    @Test
    fun `5xx keeps the event and asks for a retry`() = runBlocking {
        for (code in listOf(500, 502, 503)) {
            val queue = MessageEventQueue(MemoryStore())
            queue.enqueue(event(1))
            assertTrue("HTTP $code", queue.drain { code })
            assertEquals("HTTP $code", listOf(event(1)), queue.pending())
        }
    }

    @Test
    fun `IO error keeps the event and asks for a retry`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueue(event(1))
        assertTrue(queue.drain { throw IOException("offline") })
        assertEquals(listOf(event(1)), queue.pending())
    }

    @Test
    fun `a mixed batch drops what landed and keeps the rest`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueue(event(1))
        queue.enqueue(event(2))
        queue.enqueue(event(3))
        val codes = mapOf("ref-1" to 201, "ref-2" to 503, "ref-3" to 201)
        assertTrue(queue.drain { codes.getValue(it.client_ref) })
        // Stops at the first retryable failure: the server is likely down.
        assertEquals(listOf(event(2), event(3)), queue.pending())
    }

    @Test
    fun `an event enqueued during an upload is not lost`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueue(event(1))
        queue.drain {
            queue.enqueue(event(2))
            201
        }
        assertEquals(listOf(event(2)), queue.pending())
    }

    @Test
    fun `outcome table`() {
        for (code in listOf(200, 201, 404, 400)) {
            assertEquals("HTTP $code", MessageEventQueue.Outcome.DROP, MessageEventQueue.outcomeFor(code))
        }
        for (code in listOf(401, 403, 429, 500, 503)) {
            assertEquals("HTTP $code", MessageEventQueue.Outcome.RETRY, MessageEventQueue.outcomeFor(code))
        }
    }
}
