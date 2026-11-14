package com.mecris.go.model

import com.mecris.go.sync.ClaudePlanDto
import com.mecris.go.sync.ClaudePlanWindowDto
import java.time.Duration
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

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

/**
 * Kotlin twin of claude_plan_usage.derive_state + summarize (Python is the reference;
 * contracts/claude_plan_cases.json pins all three arms). Spin already derives the
 * state, but the dashboard caches the response, so the phone re-checks it against
 * its own clock: a reading over 24 h old, or a weekly window past its reset, is
 * 'unknown' however fresh it looked when it was cached.
 */
object ClaudePlanState {
    const val AVAILABLE = "available"
    const val CONSTRAINED = "constrained"
    const val EXHAUSTED = "exhausted"
    const val UNKNOWN = "unknown"

    private const val WEEKLY_ALL = "weekly_all"
    private const val CONSTRAINED_PCT = 80.0
    private const val EXHAUSTED_PCT = 100.0
    private val MAX_READING_AGE: Duration = Duration.ofHours(24)

    private val RESET_FORMAT: DateTimeFormatter =
        DateTimeFormatter.ofPattern("EEE h:mm a", Locale.US).withZone(ZoneId.of("America/New_York"))

    private data class Fresh(val kind: String, val pct: Double, val resetsAt: Instant)

    fun derive(plan: ClaudePlanDto?, now: Instant): ClaudePlanView {
        if (plan == null) {
            return unknown("no reading recorded", hasReading = false, plan = null, age = null, fresh = emptyList())
        }
        val observed = parseInstant(plan.observed_at)
        val age = observed?.let { Math.floorDiv(Duration.between(it, now).seconds, 60L) }
        if (observed == null || Duration.between(observed, now) > MAX_READING_AGE) {
            return unknown("reading is stale", hasReading = true, plan = plan, age = age, fresh = emptyList())
        }

        val fresh = (plan.windows ?: emptyList()).mapNotNull { it.toFresh() }.filter { it.resetsAt.isAfter(now) }
        val weekly = fresh.firstOrNull { it.kind == WEEKLY_ALL }
            ?: return unknown(
                "weekly window has reset since the last reading",
                hasReading = true, plan = plan, age = age, fresh = fresh
            )

        val worst = fresh.maxByOrNull { it.pct }!!
        val state = when {
            worst.pct >= EXHAUSTED_PCT -> EXHAUSTED
            worst.pct > CONSTRAINED_PCT -> CONSTRAINED
            else -> AVAILABLE
        }
        val resetsLabel = RESET_FORMAT.format(weekly.resetsAt)
        var line = "Claude: $state (${pct0(weekly.pct)}% weekly, resets $resetsLabel)"
        if (worst.kind != WEEKLY_ALL && state != AVAILABLE) {
            line += "; ${worst.kind} ${pct0(worst.pct)}%"
        }
        return ClaudePlanView(
            state = state,
            reason = "${worst.kind} at ${pct0(worst.pct)}%",
            stale = false,
            summaryLine = line,
            freshWindowKinds = fresh.map { it.kind },
            hasReading = true,
            plan = plan.plan,
            verified = plan.verified,
            weeklyPct = weekly.pct,
            weeklyResetsLabel = resetsLabel,
            ageMinutes = age
        )
    }

    private fun unknown(
        reason: String,
        hasReading: Boolean,
        plan: ClaudePlanDto?,
        age: Long?,
        fresh: List<Fresh>
    ) = ClaudePlanView(
        state = UNKNOWN,
        reason = reason,
        stale = true,
        summaryLine = "Claude: $UNKNOWN ($reason)",
        freshWindowKinds = fresh.map { it.kind },
        hasReading = hasReading,
        plan = plan?.plan,
        verified = plan?.verified,
        weeklyPct = null,
        weeklyResetsLabel = null,
        ageMinutes = age
    )

    private fun ClaudePlanWindowDto.toFresh(): Fresh? {
        val k = kind ?: return null
        val p = pct_used ?: return null
        val r = parseInstant(resets_at) ?: return null
        return Fresh(k, p, r)
    }

    /** No decimals, as Python's f"{x:.0f}" (contract cases avoid .5 ties). */
    private fun pct0(pct: Double): String = String.format(Locale.US, "%.0f", pct)
}

/**
 * ISO-8601 with an offset or Z; also tolerates Postgres text like
 * "2026-11-14 19:00:00.41+00" (hour-only offset), which strict parsers reject.
 */
fun parseInstant(text: String?): Instant? {
    val t = text?.trim().orEmpty()
    if (t.isEmpty()) return null
    runCatching { return OffsetDateTime.parse(t).toInstant() }
    var iso = t.replace(' ', 'T')
    if (Regex("[+-]\\d{2}$").containsMatchIn(iso)) iso += ":00"
    return runCatching { OffsetDateTime.parse(iso).toInstant() }.getOrNull()
}

/** Short age label for cards: "just now", "42m ago", "3h ago", "2d ago". */
fun formatAge(minutes: Long?): String = when {
    minutes == null -> "—"
    minutes <= 0 -> "just now"
    minutes < 60 -> "${minutes}m ago"
    minutes < 1440 -> "${minutes / 60}h ago"
    else -> "${minutes / 1440}d ago"
}
