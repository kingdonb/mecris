package com.mecris.go.health

import com.mecris.go.sync.PaceDto
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.ceil

/** Nag wording helpers (#349). Pure, so the copy is unit tested without a device. */
object NagCopy {
    private val PACE_GOALS = setOf(DelayedNagWorker.GOAL_ARABIC, DelayedNagWorker.GOAL_GREEK)
    private val CLOCK: DateTimeFormatter = DateTimeFormatter.ofPattern("h:mm a", Locale.US)
    /** Spin's pace target is 22:00 New York; used when clear_by is missing. */
    private const val DEFAULT_CLEAR_BY = "10:00 PM"

    /**
     * One line from Spin's aggregate-status pace: reviews left today and the hourly
     * pace to clear them by 22:00. Null for walk nags, a missing goal entry, or
     * nothing left, so the nag text stays as it was.
     */
    fun paceLine(goal: String, pace: List<PaceDto>?): String? {
        val key = goal.uppercase(Locale.US)
        if (key !in PACE_GOALS) return null
        val entry = pace?.firstOrNull { it.goal?.uppercase(Locale.US) == key } ?: return null
        val remaining = entry.remaining ?: return null
        if (remaining <= 0) return null

        val reviews = if (remaining == 1) "1 review" else "$remaining reviews"
        val perHour = entry.per_hour
        // Spin (pace.rs) sends per_hour == remaining when under an hour is left or
        // 22:00 has passed: the whole remainder is due now. Null or <= 0 is defensive.
        if (perHour == null || perHour <= 0.0 || perHour >= remaining) return "Pace: $reviews left today, due now."
        val rate = ceil(perHour).toInt().coerceAtLeast(1)
        return "Pace: $reviews left today, about $rate an hour to clear them by ${clearByLabel(entry.clear_by)}."
    }

    /** [message] with the pace line appended on its own line, or unchanged. */
    fun withPace(message: String, goal: String, pace: List<PaceDto>?): String =
        paceLine(goal, pace)?.let { "$message\n$it" } ?: message

    /** clear_by is ISO with New York's offset, so its own wall-clock time is the label. */
    private fun clearByLabel(clearBy: String?): String =
        clearBy?.let { runCatching { CLOCK.format(OffsetDateTime.parse(it)) }.getOrNull() } ?: DEFAULT_CLEAR_BY
}
