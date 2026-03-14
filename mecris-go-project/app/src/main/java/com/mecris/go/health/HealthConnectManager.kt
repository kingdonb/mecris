package com.mecris.go.health

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.DistanceRecord
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.time.Instant
import java.time.ZonedDateTime
import java.time.temporal.ChronoUnit

class HealthConnectManager(private val context: Context) {

    val healthConnectClient by lazy { HealthConnectClient.getOrCreate(context) }

    val permissions = setOf(
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(DistanceRecord::class),
        HealthPermission.getReadPermission(ExerciseSessionRecord::class)
    )

    private val _isSupported = MutableStateFlow(false)
    val isSupported: StateFlow<Boolean> = _isSupported

    init {
        checkAvailability()
    }

    private fun checkAvailability() {
        val availability = HealthConnectClient.getSdkStatus(context)
        _isSupported.value = availability == HealthConnectClient.SDK_AVAILABLE
    }

    suspend fun hasAllPermissions(): Boolean {
        if (!_isSupported.value) return false
        val granted = healthConnectClient.permissionController.getGrantedPermissions()
        return granted.containsAll(permissions)
    }

    suspend fun fetchRecentWalkData(): WalkDataSummary {
        val report = fetchFullActivityReport()
        val likelyWalked = report.steps > 1500 || report.walkingSessionsCount > 0
        return WalkDataSummary(
            totalSteps = report.steps,
            totalDistanceMeters = report.distanceMeters,
            isWalkInferred = likelyWalked
        )
    }

    suspend fun fetchFullActivityReport(): FullActivityReport {
        if (!hasAllPermissions()) return FullActivityReport(0, 0.0, 0, false)

        val endTime = Instant.now()
        val startTime = endTime.minus(23, ChronoUnit.HOURS)
        val timeRangeFilter = TimeRangeFilter.between(startTime, endTime)

        // 1. Read Steps
        val stepsRequest = ReadRecordsRequest(
            recordType = StepsRecord::class,
            timeRangeFilter = timeRangeFilter
        )
        val totalSteps = healthConnectClient.readRecords(stepsRequest).records.sumOf { it.count }

        // 2. Read Distance
        val distanceRequest = ReadRecordsRequest(
            recordType = DistanceRecord::class,
            timeRangeFilter = timeRangeFilter
        )
        var totalDistanceMeters = healthConnectClient.readRecords(distanceRequest).records.sumOf { it.distance.inMeters }

        // Fallback estimate
        if (totalDistanceMeters == 0.0 && totalSteps > 0) {
            totalDistanceMeters = totalSteps * 0.8
        }

        // 3. Read Exercise Sessions
        val sessionRequest = ReadRecordsRequest(
            recordType = ExerciseSessionRecord::class,
            timeRangeFilter = timeRangeFilter
        )
        val sessions = healthConnectClient.readRecords(sessionRequest).records
        val walkingSessions = sessions.filter {
            it.exerciseType == ExerciseSessionRecord.EXERCISE_TYPE_WALKING
        }

        // 4. Check for Routes
        // Note: READ_EXERCISE_ROUTES is a separate permission check
        val hasRoutes = sessions.any { it.hasRoute }

        return FullActivityReport(
            steps = totalSteps,
            distanceMeters = totalDistanceMeters,
            walkingSessionsCount = walkingSessions.size,
            hasExerciseRoutes = hasRoutes
        )
    }
}

data class WalkDataSummary(
    val totalSteps: Long,
    val totalDistanceMeters: Double,
    val isWalkInferred: Boolean
)

data class FullActivityReport(
    val steps: Long,
    val distanceMeters: Double,
    val walkingSessionsCount: Int,
    val hasExerciseRoutes: Boolean
)
