package com.mecris.go.health

import java.time.Duration
import java.time.Instant
import java.time.ZoneId

/**
 * Local walk-nag snooze written by the LATER and START notification actions
 * (#363 phase 1). DelayedNagWorker reads [PREF_KEY] from its own prefs
 * ("mecris_worker_state") before it spends weather or LLM work on a walk nag.
 *
 * Phase 2 moves the snooze decision to the cloud decider (LATER picks a time
 * that lands before dark, see docs/WALK_REMINDERS.md). Until then this is a
 * deliberately simple fixed 90 minutes, and START ends walk nags for the
 * New York day.
 */
object WalkSuppression {
    const val PREF_KEY = "walk_nag_suppressed_until"
    val LATER_SNOOZE: Duration = Duration.ofMinutes(90)

    private val ZONE: ZoneId = ZoneId.of(WorkerPolicy.WORKER_TIMEZONE)

    fun laterUntil(now: Instant): Instant = now.plus(LATER_SNOOZE)

    /** The next midnight in America/New_York after [now]. */
    fun endOfNewYorkDay(now: Instant): Instant =
        now.atZone(ZONE).toLocalDate().plusDays(1).atStartOfDay(ZONE).toInstant()

    /** A LATER after START (or a second LATER) never shortens what is already set. */
    fun merge(currentUntilMs: Long, newUntilMs: Long): Long = maxOf(currentUntilMs, newUntilMs)

    fun isSuppressed(untilMs: Long, nowMs: Long): Boolean = nowMs < untilMs
}
