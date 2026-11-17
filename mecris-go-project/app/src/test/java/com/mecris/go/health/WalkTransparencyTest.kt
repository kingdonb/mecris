package com.mecris.go.health

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

/** #62: the dashboard says where the walk numbers came from. */
class WalkTransparencyTest {

    private fun summary(
        source: String = "Health Connect (Workouts)",
        sessions: Int = 1,
        routes: Boolean = false,
        points: Int = 0,
    ) = WalkDataSummary(
        totalSteps = 3000,
        totalDistanceMeters = 2000.0,
        distanceSource = source,
        walkingSessionsCount = sessions,
        hasExerciseRoutes = routes,
        routePointCount = points,
        isWalkInferred = true,
        startTime = Instant.EPOCH,
        consentableSessionId = null,
    )

    @Test
    fun `measured distance names Health Connect and is not estimated`() {
        val t = WalkTransparency.of(summary(source = "Health Connect (Workouts)"))
        assertEquals("DISTANCE: HEALTH CONNECT (WORKOUTS)", t.distanceLabel)
        assertFalse(t.isEstimated)
    }

    @Test
    fun `distance from steps is marked estimated`() {
        val t = WalkTransparency.of(summary(source = "Estimated from Steps (0.66m)"))
        assertEquals("DISTANCE: ESTIMATED FROM STEPS", t.distanceLabel)
        assertTrue(t.isEstimated)
    }

    @Test
    fun `session count is shown even when it is zero`() {
        assertEquals("0 WALKING SESSIONS", WalkTransparency.of(summary(sessions = 0)).sessionsLabel)
        assertEquals("1 WALKING SESSION", WalkTransparency.of(summary(sessions = 1)).sessionsLabel)
        assertEquals("3 WALKING SESSIONS", WalkTransparency.of(summary(sessions = 3)).sessionsLabel)
    }

    @Test
    fun `route detection is shown with its point count`() {
        assertEquals("GPS ROUTE: 412 POINTS", WalkTransparency.of(summary(routes = true, points = 412)).routeLabel)
        assertEquals("GPS ROUTE: NONE", WalkTransparency.of(summary(routes = false)).routeLabel)
    }

    @Test
    fun `health connect unavailable is told apart from a missing permission`() {
        assertEquals(TelemetryBanner.HEALTH_CONNECT_UNAVAILABLE,
            TelemetryBanner.of(healthConnectAvailable = false, hasForegroundPermission = false))
        assertEquals(TelemetryBanner.PERMISSION_MISSING,
            TelemetryBanner.of(healthConnectAvailable = true, hasForegroundPermission = false))
        assertEquals(TelemetryBanner.NONE,
            TelemetryBanner.of(healthConnectAvailable = true, hasForegroundPermission = true))
    }

    @Test
    fun `each banner has its own message`() {
        val unavailable = TelemetryBanner.HEALTH_CONNECT_UNAVAILABLE.message
        val missing = TelemetryBanner.PERMISSION_MISSING.message
        assertTrue(unavailable.contains("Health Connect"))
        assertTrue(missing.contains("Permission"))
        assertFalse(unavailable == missing)
    }
}
