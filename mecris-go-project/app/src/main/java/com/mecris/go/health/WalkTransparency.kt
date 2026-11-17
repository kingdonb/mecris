package com.mecris.go.health

/**
 * #62: what the dashboard says about where today's walk numbers came from:
 * measured or estimated distance, how many walking sessions were found, and
 * whether a GPS route came with them.
 */
data class WalkTransparency(
    val distanceLabel: String,
    val isEstimated: Boolean,
    val sessionsLabel: String,
    val routeLabel: String,
) {
    companion object {
        fun of(summary: WalkDataSummary): WalkTransparency {
            val estimated = summary.distanceSource.startsWith("Estimated", ignoreCase = true)
            val distance = if (estimated) "ESTIMATED FROM STEPS" else summary.distanceSource.uppercase()
            val n = summary.walkingSessionsCount
            return WalkTransparency(
                distanceLabel = "DISTANCE: $distance",
                isEstimated = estimated,
                sessionsLabel = "$n WALKING SESSION${if (n == 1) "" else "S"}",
                routeLabel = if (summary.hasExerciseRoutes) "GPS ROUTE: ${summary.routePointCount} POINTS" else "GPS ROUTE: NONE",
            )
        }
    }
}

/**
 * #62: the dashboard's red banner. Health Connect being unavailable (not
 * installed, or needs an update) is a different fix from a permission the user
 * hasn't granted, so they get different messages.
 */
enum class TelemetryBanner(val message: String) {
    NONE(""),
    HEALTH_CONNECT_UNAVAILABLE("Health Connect is not available on this phone. Install or update it, then tap to check again."),
    PERMISSION_MISSING("Permission required to read steps. Tap to resolve.");

    companion object {
        fun of(healthConnectAvailable: Boolean, hasForegroundPermission: Boolean): TelemetryBanner = when {
            !healthConnectAvailable -> HEALTH_CONNECT_UNAVAILABLE
            !hasForegroundPermission -> PERMISSION_MISSING
            else -> NONE
        }
    }
}
