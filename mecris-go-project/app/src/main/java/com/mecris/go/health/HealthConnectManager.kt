package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.DistanceRecord
import androidx.health.connect.client.records.ExerciseRouteResult
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.temporal.ChronoUnit

class HealthConnectManager(private val context: Context) {

    val healthConnectClient by lazy { HealthConnectClient.getOrCreate(context) }

    val foregroundPermissions = setOf(
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(DistanceRecord::class),
        HealthPermission.getReadPermission(ExerciseSessionRecord::class),
        // CRITICAL: Explicitly request Route permission
        "android.permission.health.READ_EXERCISE_ROUTES"
    )

    // Special background permission
    val backgroundPermission = "android.permission.health.READ_HEALTH_DATA_IN_BACKGROUND"

    private val _isSupported = MutableStateFlow(false)
    val isSupported: StateFlow<Boolean> = _isSupported

    init {
        checkAvailability()
    }

    private fun checkAvailability() {
        val availability = HealthConnectClient.getSdkStatus(context)
        _isSupported.value = availability == HealthConnectClient.SDK_AVAILABLE
    }

    suspend fun hasForegroundPermissions(): Boolean {
        if (!_isSupported.value) return false
        val granted = healthConnectClient.permissionController.getGrantedPermissions()
        // Check if all foreground permissions are in the granted set
        return granted.containsAll(foregroundPermissions)
    }

    suspend fun hasBackgroundPermission(): Boolean {
        if (!_isSupported.value) return false
        val granted = healthConnectClient.permissionController.getGrantedPermissions()
        return granted.contains(backgroundPermission)
    }

    suspend fun fetchRecentWalkData(): WalkDataSummary {
        val report = fetchFullActivityReport()
        val likelyWalked = report.steps > 1500 || report.walkingSessionsCount > 0
        return WalkDataSummary(
            totalSteps = report.steps,
            totalDistanceMeters = report.distanceMeters,
            distanceSource = report.distanceSource,
            walkingSessionsCount = report.walkingSessionsCount,
            hasExerciseRoutes = report.hasExerciseRoutes,
            routePointCount = report.routePointCount,
            isWalkInferred = likelyWalked
        )
    }

    suspend fun fetchFullActivityReport(): FullActivityReport {
        if (!hasForegroundPermissions()) {
            Log.w("HealthConnectManager", "Missing foreground permissions for full report")
            return FullActivityReport(0, 0.0, "None", 0, false, 0)
        }

        // Use Start of Day in local timezone for "Today's" metrics
        val now = Instant.now()
        val startOfDay = LocalDateTime.now().withHour(0).withMinute(0).withSecond(0)
            .atZone(ZoneId.systemDefault()).toInstant()
        
        // Look back at least 24 hours to ensure we catch yesterday's walk if it's early
        val startTime = now.minus(24, ChronoUnit.HOURS)
        val timeRangeFilter = TimeRangeFilter.between(startTime, now)

        Log.d("HealthConnectManager", "Querying Health Connect from $startTime to $now")

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
        val distanceRecords = healthConnectClient.readRecords(distanceRequest).records
        var totalDistanceMeters = distanceRecords.sumOf { it.distance.inMeters }
        var source = "Health Connect (Passive)"

        // 3. Read Exercise Sessions
        val sessionRequest = ReadRecordsRequest(
            recordType = ExerciseSessionRecord::class,
            timeRangeFilter = timeRangeFilter
        )
        val sessions = healthConnectClient.readRecords(sessionRequest).records
        val walkingSessions = sessions.filter {
            it.exerciseType == ExerciseSessionRecord.EXERCISE_TYPE_WALKING
        }

        Log.d("HealthConnectManager", "Found ${walkingSessions.size} walking sessions")

        // 4. Check for Routes and extract Point Count
        var hasRoutes = false
        var totalRoutePoints = 0
        
        walkingSessions.forEach { session ->
            val routeResult = session.exerciseRouteResult
            if (routeResult is ExerciseRouteResult.Data) {
                hasRoutes = true
                totalRoutePoints += routeResult.exerciseRoute.locations.size
                Log.d("HealthConnectManager", "Session ${session.metadata.id} has route with ${routeResult.exerciseRoute.locations.size} points")
            } else if (routeResult is ExerciseRouteResult.ConsentRequired) {
                Log.w("HealthConnectManager", "Route consent required for session ${session.metadata.id}")
            }
        }

        // Source priority logic
        if (walkingSessions.isNotEmpty()) {
            source = "Health Connect (Walking Session)"
            // If sessions exist, we might want to prioritize the distance associated with them
            // But for now, we'll keep the aggregate distance if it's non-zero
        }

        // Fallback estimate if all else fails
        if (totalDistanceMeters == 0.0 && totalSteps > 0) {
            totalDistanceMeters = totalSteps * 0.66
            source = "Estimated from Steps (0.66m)"
        } else if (totalDistanceMeters == 0.0) {
            source = "No Data"
        }

        return FullActivityReport(
            steps = totalSteps,
            distanceMeters = totalDistanceMeters,
            distanceSource = source,
            walkingSessionsCount = walkingSessions.size,
            hasExerciseRoutes = hasRoutes,
            routePointCount = totalRoutePoints
        )
    }
}

data class WalkDataSummary(
    val totalSteps: Long,
    val totalDistanceMeters: Double,
    val distanceSource: String,
    val walkingSessionsCount: Int,
    val hasExerciseRoutes: Boolean,
    val routePointCount: Int,
    val isWalkInferred: Boolean
)

data class FullActivityReport(
    val steps: Long,
    val distanceMeters: Double,
    val distanceSource: String,
    val walkingSessionsCount: Int,
    val hasExerciseRoutes: Boolean,
    val routePointCount: Int
)
