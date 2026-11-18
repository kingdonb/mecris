package com.mecris.go.sync

import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/**
 * #395: what the background worker's last run did, sent with the heartbeat so the
 * system pulse can show it. Rules: contracts/spin_heartbeat_request.json.
 */
object HeartbeatStatus {
    const val MAX_CHARS = 160
    private val HHMM = DateTimeFormatter.ofPattern("HH:mm")

    /** Trimmed and cut to MAX_CHARS; blank is absent. */
    fun clean(value: String?): String? = value?.trim()?.takeIf { it.isNotEmpty() }?.take(MAX_CHARS)

    /** e.g. "run 14:05 ET: success (auth,hb,helix)". [atEt] is already in New York time. */
    fun describe(atEt: ZonedDateTime, result: String, phases: List<String>): String =
        "run ${atEt.format(HHMM)} ET: $result (${phases.joinToString(",")})".take(MAX_CHARS)
}
