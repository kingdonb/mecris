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

    // Level 1: Core permissions required for basic dashboard
    val foregroundPermissions = setOf(
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(DistanceRecord::class),
        HealthPermission.getReadPermission(ExerciseSessionRecord::class)
    )

    // Level 2: High-sensitivity route permission
    val routePermission = "android.permission.health.READ_EXERCISE_ROUTES"

    // Level 3: Background permission
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
        // Allow the app to proceed if at least Steps and Distance are granted.
        // We will just have degraded functionality (no sessions/routes) if Exercise is missing.
        val coreGranted = granted.contains(HealthPermission.getReadPermission(StepsRecord::class)) &&
                          granted.contains(HealthPermission.getReadPermission(DistanceRecord::class))
        return coreGranted
    }

    suspend fun hasRoutePermission(): Boolean {
        if (!_isSupported.value) return false
        val granted = healthConnectClient.permissionController.getGrantedPermissions()
        return granted.contains(routePermission)
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
            isWalkInferred = likelyWalked,
            startTime = report.startTime
        )
    }

    suspend fun fetchFullActivityReport(): FullActivityReport {
        if (!hasForegroundPermissions()) {
            Log.w("HealthConnectManager", "Missing foreground permissions for full report")
            return FullActivityReport(0, 0.0, "None", 0, false, 0, Instant.now())
        }

        val now = Instant.now()
        // Stabilize start time to the beginning of the current hour for idempotency fallback
        val fallbackStart = now.truncatedTo(ChronoUnit.HOURS)
        val localDateTime = LocalDateTime.ofInstant(now, ZoneId.systemDefault())
        val startOfToday = localDateTime.toLocalDate().atStartOfDay(ZoneId.systemDefault()).toInstant()
        val queryStart = startOfToday
        val timeRangeFilter = TimeRangeFilter.between(queryStart, now)

        Log.d("HealthConnectManager", "Querying Health Connect from $queryStart to $now")

        // ... existing record reading logic ...
        // (I will keep the existing logic but ensure startTime is captured from sessions if available)
        
        // 3. Read Exercise Sessions
        val sessionRequest = ReadRecordsRequest(
            recordType = ExerciseSessionRecord::class,
            timeRangeFilter = timeRangeFilter
        )
        val sessions = healthConnectClient.readRecords(sessionRequest).records
        Log.d("HealthConnectManager", "Total exercise sessions found: ${sessions.size}")
        
        val walkingSessions = sessions.filter {
            it.exerciseType == ExerciseSessionRecord.EXERCISE_TYPE_WALKING
        }
        Log.d("HealthConnectManager", "Walking sessions found: ${walkingSessions.size}")
        
        // Use the earliest walking session start time if available, otherwise fallback
        val effectiveStartTime = walkingSessions.minByOrNull { it.startTime }?.startTime ?: fallbackStart

        // 1. Read Steps
        val stepsRequest = ReadRecordsRequest(recordType = StepsRecord::class, timeRangeFilter = timeRangeFilter)
        val stepsRecords = healthConnectClient.readRecords(stepsRequest).records
        val totalSteps = stepsRecords.sumOf { it.count }

        // 2. Read Distance
        val distanceRequest = ReadRecordsRequest(recordType = DistanceRecord::class, timeRangeFilter = timeRangeFilter)
        // Wait, I should use the same timeRangeFilter as above for consistency
        val distanceRecords = healthConnectClient.readRecords(distanceRequest).records
        var totalDistanceMeters = distanceRecords.sumOf { it.distance.inMeters }
        var source = if (totalDistanceMeters > 0) "Health Connect (Distance)" else "Health Connect (Passive)"

        // 4. Check for Routes
        var hasRoutes = false
        var totalRoutePoints = 0
        walkingSessions.forEach { session ->
            when (val routeResult = session.exerciseRouteResult) {
                is ExerciseRouteResult.Data -> {
                    hasRoutes = true
                    totalRoutePoints += routeResult.exerciseRoute.route.size
                    Log.d("HealthConnectManager", "Found route with ${routeResult.exerciseRoute.route.size} points")
                }
                is ExerciseRouteResult.NoData -> {
                    Log.d("HealthConnectManager", "No route data for session ${session.metadata.id}")
                }
                is ExerciseRouteResult.ConsentRequired -> {
                    Log.w("HealthConnectManager", "Route consent required for session ${session.metadata.id}")
                }
            }
        }

        if (walkingSessions.isNotEmpty()) { source = "Health Connect (Walking Session)" }
        if (totalDistanceMeters == 0.0 && totalSteps > 0) {
            totalDistanceMeters = totalSteps * 0.66
            source = "Estimated from Steps (0.66m)"
        }

        return FullActivityReport(
            steps = totalSteps,
            distanceMeters = totalDistanceMeters,
            distanceSource = source,
            walkingSessionsCount = walkingSessions.size,
            hasExerciseRoutes = hasRoutes,
            routePointCount = totalRoutePoints,
            startTime = effectiveStartTime
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
    val isWalkInferred: Boolean,
    val startTime: Instant
)

data class FullActivityReport(
    val steps: Long,
    val distanceMeters: Double,
    val distanceSource: String,
    val walkingSessionsCount: Int,
    val hasExerciseRoutes: Boolean,
    val routePointCount: Int,
    val startTime: Instant
)
