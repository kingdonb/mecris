package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.*
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
        val stepsGranted = granted.contains(HealthPermission.getReadPermission(StepsRecord::class))
        val distGranted = granted.contains(HealthPermission.getReadPermission(DistanceRecord::class))
        val exerciseGranted = granted.contains(HealthPermission.getReadPermission(ExerciseSessionRecord::class))
        Log.d("HealthConnectManager", "PERM DIAG: Steps=$stepsGranted, Distance=$distGranted, Exercise=$exerciseGranted")
        return stepsGranted && distGranted && exerciseGranted
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

    private suspend fun fetchFullActivityReport(): FullActivityReport {
        val now = Instant.now()
        val monthAgo = now.minus(30, ChronoUnit.DAYS)
        val monthFilter = TimeRangeFilter.between(monthAgo, now)
        
        // 0. Deep Diagnostics
        try {
            val sessions = healthConnectClient.readRecords(ReadRecordsRequest(ExerciseSessionRecord::class, monthFilter)).records
            Log.d("HealthConnectManager", "DIAGNOSTIC: Found ${sessions.size} sessions in last 30d")
            if (sessions.isNotEmpty()) {
                val types = sessions.map { it.exerciseType }.distinct()
                val sources = sessions.map { it.metadata.dataOrigin.packageName }.distinct()
                Log.d("HealthConnectManager", "DIAGNOSTIC: Session types=$types, sources=$sources")
            }
            val stepsRecords = healthConnectClient.readRecords(ReadRecordsRequest(StepsRecord::class, monthFilter)).records
            if (stepsRecords.isNotEmpty()) {
                val sources = stepsRecords.map { it.metadata.dataOrigin.packageName }.distinct()
                Log.d("HealthConnectManager", "DIAGNOSTIC: Steps sources found: $sources")
            }
        } catch (e: Exception) { Log.e("HealthConnectManager", "Diag Failed: ${e.message}") }

        if (!hasForegroundPermissions()) {
            return FullActivityReport(0, 0.0, "Permission Denied", 0, false, 0, now)
        }

        val localDateTime = LocalDateTime.ofInstant(now, ZoneId.systemDefault())
        val startOfToday = localDateTime.toLocalDate().atStartOfDay(ZoneId.systemDefault()).toInstant()
        val queryStart = startOfToday
        val timeRangeFilter = TimeRangeFilter.between(queryStart, now)
        val fallbackStart = now.truncatedTo(ChronoUnit.HOURS)

        // 1. Baseline: Generic daily counts
        val genericSteps = healthConnectClient.readRecords(ReadRecordsRequest(StepsRecord::class, timeRangeFilter)).records.sumOf { it.count }
        val genericDistance = healthConnectClient.readRecords(ReadRecordsRequest(DistanceRecord::class, timeRangeFilter)).records.sumOf { it.distance.inMeters }
        
        // 2. Specialized: Explicit sessions
        val sessions = healthConnectClient.readRecords(ReadRecordsRequest(ExerciseSessionRecord::class, timeRangeFilter)).records
        val walkingSessions = sessions.filter {
            it.exerciseType == ExerciseSessionRecord.EXERCISE_TYPE_WALKING ||
            it.exerciseType == ExerciseSessionRecord.EXERCISE_TYPE_OTHER_WORKOUT
        }
        
        var totalSteps = genericSteps
        var totalDistanceMeters = genericDistance
        var source = if (totalDistanceMeters > 0) "Health Connect (Distance)" else "Health Connect (Passive)"

        // Comparison Logic: Don't sum, choose the better data source
        if (walkingSessions.isNotEmpty()) {
            val sessionSteps = walkingSessions.sumOf { s ->
                healthConnectClient.readRecords(ReadRecordsRequest(StepsRecord::class, TimeRangeFilter.between(s.startTime, s.endTime))).records.sumOf { it.count }
            }
            val sessionDist = walkingSessions.sumOf { s ->
                healthConnectClient.readRecords(ReadRecordsRequest(DistanceRecord::class, TimeRangeFilter.between(s.startTime, s.endTime))).records.sumOf { it.distance.inMeters }
            }

            // If sessions provide MORE or EQUAL data, prioritize them as higher quality
            if (sessionSteps >= totalSteps) {
                totalSteps = sessionSteps
                source = "Health Connect (Walking Session)"
            }
            if (sessionDist >= totalDistanceMeters) {
                totalDistanceMeters = sessionDist
                source = "Health Connect (Walking Session)"
            }
        }

        // 3. Route Points
        var hasRoutes = false
        var totalRoutePoints = 0
        walkingSessions.forEach { session ->
            when (val routeResult = session.exerciseRouteResult) {
                is ExerciseRouteResult.Data -> {
                    hasRoutes = true
                    totalRoutePoints += routeResult.exerciseRoute.route.size
                }
                else -> {}
            }
        }

        // 4. Final Fallback for missing distance
        if (totalDistanceMeters == 0.0 && totalSteps > 0) {
            totalDistanceMeters = totalSteps * 0.66
            source = "Estimated from Steps (0.66m)"
        }

        val effectiveStartTime = walkingSessions.minByOrNull { it.startTime }?.startTime ?: fallbackStart

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

private data class FullActivityReport(
    val steps: Long,
    val distanceMeters: Double,
    val distanceSource: String,
    val walkingSessionsCount: Int,
    val hasExerciseRoutes: Boolean,
    val routePointCount: Int,
    val startTime: Instant
)
