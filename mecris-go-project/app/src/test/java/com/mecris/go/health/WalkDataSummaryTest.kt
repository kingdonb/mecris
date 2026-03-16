package com.mecris.go.health

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertFalse
import org.junit.Test
import java.time.Instant

class WalkDataSummaryTest {

    @Test
    fun `isWalkInferred is true when totalSteps over 1500`() {
        val summary = WalkDataSummary(
            totalSteps = 1501,
            totalDistanceMeters = 1000.0,
            distanceSource = "Test",
            walkingSessionsCount = 0,
            hasExerciseRoutes = false,
            routePointCount = 0,
            isWalkInferred = true,
            startTime = Instant.now()
        )
        
        assertTrue(summary.isWalkInferred)
    }

    @Test
    fun `isWalkInferred is true when walkingSessionsCount over 0`() {
        val summary = WalkDataSummary(
            totalSteps = 500,
            totalDistanceMeters = 300.0,
            distanceSource = "Test",
            walkingSessionsCount = 1,
            hasExerciseRoutes = false,
            routePointCount = 0,
            isWalkInferred = true,
            startTime = Instant.now()
        )
        
        assertTrue(summary.isWalkInferred)
    }
}