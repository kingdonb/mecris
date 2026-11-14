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

object SystemPulse {
    fun rows(status: AggregateStatusResponseDto?): List<PulseRow> = TODO("#346")
}
