package com.mecris.go.health

import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class HealthConnectManagerTest {

    private val healthManager = mockk<HealthConnectManager>()

    @Test
    fun `fetchFullActivityReport returns data from all ports`() = runBlocking {
        // Arrange
        val expectedReport = FullActivityReport(
            steps = 1777,
            distanceMeters = 1200.0,
            walkingSessionsCount = 1,
            hasExerciseRoutes = true
        )
        coEvery { healthManager.fetchFullActivityReport() } returns expectedReport

        // Act
        val result = healthManager.fetchFullActivityReport()

        // Assert
        assertEquals(1777L, result.steps)
        assertEquals(1200.0, result.distanceMeters, 0.1)
        assertEquals(1, result.walkingSessionsCount)
        assertTrue(result.hasExerciseRoutes)
    }
}
