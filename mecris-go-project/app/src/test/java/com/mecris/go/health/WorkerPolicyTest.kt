package com.mecris.go.health

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class WorkerPolicyTest {

    // --- Quiet hours: nag/debt phase window is [08:00, 22:00) ET ---

    @Test
    fun `quiet hours before 8am`() {
        assertTrue(WorkerPolicy.isQuietHours(7))
        assertTrue(WorkerPolicy.isQuietHours(0))
        assertTrue(WorkerPolicy.isQuietHours(3))
    }

    @Test
    fun `waking hours between 8 and 21 inclusive`() {
        assertFalse(WorkerPolicy.isQuietHours(8))
        assertFalse(WorkerPolicy.isQuietHours(12))
        assertFalse(WorkerPolicy.isQuietHours(21))
    }

    @Test
    fun `quiet hours from 22 onwards`() {
        assertTrue(WorkerPolicy.isQuietHours(22))
        assertTrue(WorkerPolicy.isQuietHours(23))
    }

    // --- Helix balance doorbell throttle: >= 60 min gap, waking hours only ---

    @Test
    fun `helix request allowed after interval elapsed during day`() {
        val now = 10_000_000_000L
        assertTrue(WorkerPolicy.shouldRequestHelixBalance(0L, now, 12))
        assertTrue(WorkerPolicy.shouldRequestHelixBalance(now - WorkerPolicy.HELIX_REQUEST_INTERVAL_MS, now, 12))
        assertTrue(WorkerPolicy.shouldRequestHelixBalance(now - 2 * WorkerPolicy.HELIX_REQUEST_INTERVAL_MS, now, 12))
    }

    @Test
    fun `helix request throttled within the hour`() {
        val now = 10_000_000_000L
        assertFalse(WorkerPolicy.shouldRequestHelixBalance(now - 59 * 60 * 1000L, now, 12))
        assertFalse(WorkerPolicy.shouldRequestHelixBalance(now - 1000L, now, 12))
    }

    @Test
    fun `helix request never during quiet hours even if interval elapsed`() {
        val now = 10_000_000_000L
        assertFalse(WorkerPolicy.shouldRequestHelixBalance(0L, now, 3))
        assertFalse(WorkerPolicy.shouldRequestHelixBalance(0L, now, 22))
        assertFalse(WorkerPolicy.shouldRequestHelixBalance(0L, now, 7))
    }

    // --- ET clock mapping (DST-aware; Oct 2026 is EDT = UTC-4, Jan is EST = UTC-5) ---

    @Test
    fun `current et hour maps summer instant correctly`() {
        // 2026-10-03T12:00:00Z = 08:00 EDT
        val hour = WorkerPolicy.currentEtHour(Instant.parse("2026-10-03T12:00:00Z"))
        assertTrue("Expected 8, got $hour", hour == 8)
    }

    @Test
    fun `current et hour maps winter instant correctly`() {
        // 2026-01-15T05:00:00Z = 00:00 EST
        val hour = WorkerPolicy.currentEtHour(Instant.parse("2026-01-15T05:00:00Z"))
        assertTrue("Expected 0, got $hour", hour == 0)
    }

    @Test
    fun `quiet hours boundary matches et clock`() {
        // 2026-10-03T02:30:00Z = 22:30 EDT → quiet
        assertTrue(WorkerPolicy.isQuietHours(WorkerPolicy.currentEtHour(Instant.parse("2026-10-03T02:30:00Z"))))
        // 2026-10-03T12:00:00Z = 08:00 EDT → awake
        assertFalse(WorkerPolicy.isQuietHours(WorkerPolicy.currentEtHour(Instant.parse("2026-10-03T12:00:00Z"))))
    }
}
