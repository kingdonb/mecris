package com.mecris.go.health

import java.time.Duration
import java.time.Instant

/** Local walk-nag snooze written by the LATER and START actions (#363 phase 1). */
object WalkSuppression {
    const val PREF_KEY = "walk_nag_suppressed_until"
    val LATER_SNOOZE: Duration = Duration.ofMinutes(90)

    fun laterUntil(now: Instant): Instant = now

    fun endOfNewYorkDay(now: Instant): Instant = now

    fun merge(currentUntilMs: Long, newUntilMs: Long): Long = newUntilMs

    fun isSuppressed(untilMs: Long, nowMs: Long): Boolean = false
}
