package com.mecris.go.sync

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException
import java.time.Instant

/**
 * #363 phase 1: the durable nag queue. Each nag's shown row (POST /internal/log-message)
 * goes first; its events (POST /internal/log-message-event) wait behind it, because
 * Spin answers 404 for an event whose nag it hasn't seen.
 */
class MessageEventQueueTest {

    private class MemoryStore : MessageEventQueue.Store {
        var json: String? = null
        override fun read(): String? = json
        override fun write(json: String) { this.json = json }
    }

    private fun shown(ref: String) =
        LogMessageRequestDto.shownNag("walk_reminder", Instant.parse("2026-11-15T19:00:00Z"), ref)

    private fun event(ref: String, kind: String = NagEvents.TAPPED, minute: Int = 1) =
        MessageEventRequestDto(client_ref = ref, event = kind, at = "2026-11-15T19:0$minute:00Z")

    /** Records the call order; answers from the maps (default 201). */
    private class Server(
        val shownCodes: Map<String, Int> = emptyMap(),
        val eventCodes: Map<String, Int> = emptyMap(),
        val shownThrows: Set<String> = emptySet()
    ) {
        val calls = mutableListOf<String>()
        val sendShown: suspend (LogMessageRequestDto) -> Int = {
            calls.add("shown:${it.client_ref}")
            if (it.client_ref in shownThrows) throw IOException("offline")
            shownCodes[it.client_ref] ?: 201
        }
        val sendEvent: suspend (MessageEventRequestDto) -> Int = {
            calls.add("event:${it.client_ref}:${it.event}")
            eventCodes["${it.client_ref}:${it.event}"] ?: 201
        }
    }

    private suspend fun MessageEventQueue.drain(server: Server) = drain(server.sendShown, server.sendEvent)

    // --- persistence and cap ---

    @Test
    fun `shown rows and events persist through the store`() {
        val store = MemoryStore()
        MessageEventQueue(store).enqueueShown(shown("a"))
        MessageEventQueue(store).enqueue(event("a"))
        val queue = MessageEventQueue(store)
        assertEquals(listOf(shown("a")), queue.pendingShown())
        assertEquals(listOf(event("a")), queue.pendingEvents())
    }

    @Test
    fun `cap evicts the oldest whole nag, never orphaning its events`() {
        val queue = MessageEventQueue(MemoryStore(), cap = 4)
        queue.enqueueShown(shown("a"))
        queue.enqueue(event("a", NagEvents.TAPPED))
        queue.enqueue(event("a", NagEvents.DISMISSED, 2))
        queue.enqueueShown(shown("b"))
        queue.enqueue(event("b"))
        assertEquals(listOf(shown("b")), queue.pendingShown())
        assertEquals(listOf(event("b")), queue.pendingEvents())
    }

    @Test
    fun `default cap is 200 items`() {
        val queue = MessageEventQueue(MemoryStore())
        (1..250).forEach { queue.enqueue(event("ref-$it")) }
        assertEquals(200, queue.pendingEvents().size)
        assertEquals("ref-51", queue.pendingEvents().first().client_ref)
    }

    @Test
    fun `a corrupt store reads as empty`() {
        val queue = MessageEventQueue(MemoryStore().apply { json = "{not json" })
        assertEquals(emptyList<MessageEventRequestDto>(), queue.pendingEvents())
        assertEquals(emptyList<LogMessageRequestDto>(), queue.pendingShown())
    }

    // --- ordering: shown first ---

    @Test
    fun `shown goes first, then that nag's events in order`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueueShown(shown("a"))
        queue.enqueue(event("a", NagEvents.TAPPED))
        queue.enqueue(event("a", NagEvents.ACTION_START, 2))
        val server = Server()

        assertFalse(queue.drain(server))
        assertEquals(listOf("shown:a", "event:a:tapped", "event:a:action_start"), server.calls)
        assertTrue(queue.pending().isEmpty())
    }

    @Test
    fun `an event queued before its shown row (tap race) still waits for it`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueue(event("a"))
        queue.enqueueShown(shown("a"))
        val server = Server()

        queue.drain(server)
        assertEquals(listOf("shown:a", "event:a:tapped"), server.calls)
    }

    @Test
    fun `200 Already logged counts as done`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueueShown(shown("a"))
        queue.enqueue(event("a"))
        val server = Server(shownCodes = mapOf("a" to 200))

        assertFalse(queue.drain(server))
        assertEquals(listOf("shown:a", "event:a:tapped"), server.calls)
        assertTrue(queue.pending().isEmpty())
    }

    @Test
    fun `5xx on shown holds its events back and keeps everything`() = runBlocking {
        for (code in listOf(500, 503)) {
            val queue = MessageEventQueue(MemoryStore())
            queue.enqueueShown(shown("a"))
            queue.enqueue(event("a"))
            val server = Server(shownCodes = mapOf("a" to code))

            assertTrue("HTTP $code", queue.drain(server))
            assertEquals("HTTP $code", listOf("shown:a"), server.calls)
            assertEquals(listOf(shown("a")), queue.pendingShown())
            assertEquals(listOf(event("a")), queue.pendingEvents())
        }
    }

    @Test
    fun `IO error on shown holds its events back`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueueShown(shown("a"))
        queue.enqueue(event("a"))
        val server = Server(shownThrows = setOf("a"))

        assertTrue(queue.drain(server))
        assertEquals(listOf("shown:a"), server.calls)
        assertEquals(2, queue.pending().size)
    }

    @Test
    fun `400 or 404 on shown drops the nag and its events, unsent`() = runBlocking {
        for (code in listOf(400, 404)) {
            val queue = MessageEventQueue(MemoryStore())
            queue.enqueueShown(shown("a"))
            queue.enqueue(event("a"))
            queue.enqueueShown(shown("b"))
            val server = Server(shownCodes = mapOf("a" to code))

            assertFalse("HTTP $code", queue.drain(server))
            assertEquals("HTTP $code", listOf("shown:a", "shown:b"), server.calls)
            assertTrue("HTTP $code", queue.pending().isEmpty())
        }
    }

    // --- events ---

    @Test
    fun `an event whose shown row already landed goes straight out`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueue(event("a"))
        val server = Server()
        assertFalse(queue.drain(server))
        assertEquals(listOf("event:a:tapped"), server.calls)
    }

    @Test
    fun `200, 201 and 404 drop an event`() = runBlocking {
        for (code in listOf(200, 201, 404)) {
            val queue = MessageEventQueue(MemoryStore())
            queue.enqueue(event("a"))
            assertFalse("HTTP $code", queue.drain(Server(eventCodes = mapOf("a:tapped" to code))))
            assertTrue("HTTP $code", queue.pending().isEmpty())
        }
    }

    @Test
    fun `5xx on an event keeps it after its shown row landed`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueueShown(shown("a"))
        queue.enqueue(event("a"))
        assertTrue(queue.drain(Server(eventCodes = mapOf("a:tapped" to 503))))
        assertEquals(emptyList<LogMessageRequestDto>(), queue.pendingShown())
        assertEquals(listOf(event("a")), queue.pendingEvents())
    }

    @Test
    fun `IO error on an event keeps it`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueue(event("a"))
        assertTrue(queue.drain({ 201 }, { throw IOException("offline") }))
        assertEquals(listOf(event("a")), queue.pendingEvents())
    }

    @Test
    fun `items queued during an upload are kept`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueue(event("a"))
        queue.drain({ 201 }, {
            queue.enqueue(event("b"))
            201
        })
        assertEquals(listOf(event("b")), queue.pendingEvents())
    }

    @Test
    fun `an event queued during the upload of a refused nag is dropped with it`() = runBlocking {
        val queue = MessageEventQueue(MemoryStore())
        queue.enqueueShown(shown("a"))
        queue.drain({
            queue.enqueue(event("a"))
            404
        }, { 201 })
        assertTrue(queue.pending().isEmpty())
    }

    @Test
    fun `outcome table`() {
        for (code in listOf(200, 201, 204)) {
            assertEquals("HTTP $code", MessageEventQueue.Outcome.DONE, MessageEventQueue.outcomeFor(code))
        }
        for (code in listOf(400, 404)) {
            assertEquals("HTTP $code", MessageEventQueue.Outcome.DROP, MessageEventQueue.outcomeFor(code))
        }
        for (code in listOf(401, 403, 429, 500, 503)) {
            assertEquals("HTTP $code", MessageEventQueue.Outcome.RETRY, MessageEventQueue.outcomeFor(code))
        }
    }
}
