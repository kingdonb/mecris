package com.mecris.go.sync

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.UUID

/** #363 phase 1: client_ref generation and the contract's client_ref_rule. */
class NagEventsTest {

    @Test
    fun `newClientRef is a random UUID string`() {
        val ref = NagEvents.newClientRef()
        assertEquals(36, ref.length)
        assertEquals(ref, UUID.fromString(ref).toString())
    }

    @Test
    fun `two nags never share a client_ref`() {
        val refs = (1..500).map { NagEvents.newClientRef() }.toSet()
        assertEquals(500, refs.size)
        assertNotEquals(NagEvents.newClientRef(), NagEvents.newClientRef())
    }

    @Test
    fun `a generated client_ref passes the contract rule`() {
        repeat(50) { assertTrue(NagEvents.isValidClientRef(NagEvents.newClientRef())) }
    }

    @Test
    fun `client_ref rule is 1-64 chars of letters, digits and hyphens`() {
        assertTrue(NagEvents.isValidClientRef("a"))
        assertTrue(NagEvents.isValidClientRef("A-9"))
        assertTrue(NagEvents.isValidClientRef("x".repeat(64)))
        assertFalse(NagEvents.isValidClientRef(null))
        assertFalse(NagEvents.isValidClientRef(""))
        assertFalse(NagEvents.isValidClientRef("x".repeat(65)))
        assertFalse(NagEvents.isValidClientRef("a b"))
        assertFalse(NagEvents.isValidClientRef("a_b"))
        assertFalse(NagEvents.isValidClientRef("abc\n"))
    }
}
