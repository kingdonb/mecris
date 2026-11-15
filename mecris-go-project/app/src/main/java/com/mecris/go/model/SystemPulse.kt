package com.mecris.go.model

import com.mecris.go.sync.AggregateStatusResponseDto

/** One line of the phone's system-pulse card (#346, #245). */
data class PulseRow(
    val role: String,
    val status: String,
    val age: String,
    /** The cloud cron's latest outcome line, when Spin reports one. */
    val lastStatus: String?
)

/**
 * Spin applies contracts/pulse_roles.json (which roles show, display names, status
 * thresholds), so the phone renders its rows as given, in Spin's order.
 */
object SystemPulse {
    fun rows(status: AggregateStatusResponseDto?): List<PulseRow> =
        status?.modalities.orEmpty().mapNotNull { m ->
            val role = m.role?.trim().takeUnless { it.isNullOrEmpty() } ?: return@mapNotNull null
            PulseRow(
                role = role,
                status = m.status?.trim().takeUnless { it.isNullOrEmpty() } ?: "unknown",
                age = formatAge(m.minutes_since),
                lastStatus = m.last_status?.trim().takeUnless { it.isNullOrEmpty() }
            )
        }
}
