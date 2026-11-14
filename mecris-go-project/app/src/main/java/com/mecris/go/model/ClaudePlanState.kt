package com.mecris.go.model

import com.mecris.go.sync.ClaudePlanDto
import java.time.Instant

/** What the Claude plan card renders, re-derived against the phone's clock (#344). */
data class ClaudePlanView(
    val state: String,
    val reason: String,
    val stale: Boolean,
    val summaryLine: String,
    val freshWindowKinds: List<String>,
    val hasReading: Boolean,
    val plan: String?,
    val verified: Boolean?,
    /** The fresh weekly_all window's percentage, or null when there is none. */
    val weeklyPct: Double?,
    /** The fresh weekly_all reset in New York time, e.g. "Mon 4:00 AM". */
    val weeklyResetsLabel: String?,
    /** Whole minutes since observed_at, or null without a parsable reading. */
    val ageMinutes: Long?
)

object ClaudePlanState {
    fun derive(plan: ClaudePlanDto?, now: Instant): ClaudePlanView = TODO("#344")
}

/** Short age label for cards: "just now", "42m ago", "3h ago", "2d ago". */
fun formatAge(minutes: Long?): String = TODO("#344")
