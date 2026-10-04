package com.mecris.go.health

import java.time.Instant
import java.time.ZoneId

/**
 * Pure policy gates for the background workers (task 000622 battery diet).
 * Deliberately free of Android/framework calls so JVM unit tests can exercise
 * them directly. The timezone is hardcoded to the operator's zone by design —
 * the system axiomatically has one user (see knowledge/decisions/2026-10-01).
 */
object WorkerPolicy {
    const val WORKER_TIMEZONE = "America/New_York"

    /** First hour (inclusive) at which the debt/nag phase may run. */
    const val QUIET_HOURS_START = 8

    /** Hour at which the debt/nag phase closes (exclusive; last allowed hour is 21). */
    const val QUIET_HOURS_END = 22

    /** Minimum gap between Helix balance doorbell requests. */
    const val HELIX_REQUEST_INTERVAL_MS = 60L * 60 * 1000

    fun currentEtHour(now: Instant = Instant.now()): Int =
        now.atZone(ZoneId.of(WORKER_TIMEZONE)).hour

    /** True when the debt/nag phase must NOT run (outside 08:00–22:00 ET). */
    fun isQuietHours(hour: Int): Boolean = hour < QUIET_HOURS_START || hour >= QUIET_HOURS_END

    /**
     * Helix balance doorbell gate: at most one request per interval, waking hours
     * only. The edge runs its upstream Helix fetch inline in this request, so
     * throttling here also saves radio time on the phone.
     */
    fun shouldRequestHelixBalance(lastRequestMs: Long, nowMs: Long, hour: Int): Boolean =
        !isQuietHours(hour) && (nowMs - lastRequestMs) >= HELIX_REQUEST_INTERVAL_MS
}
