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

    // Level 1: Core permissions
    val foregroundPermissions = setOf(
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(DistanceRecord::class),
        HealthPermission.getReadPermission(ExerciseSessionRecord::class),
        HealthPermission.getReadPermission(TotalCaloriesBurnedRecord::class)
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
        
        // 0. Extreme Diagnostic: Scan last 30 days for ANYTHING
        try {
            val monthAgo = now.minus(30, ChronoUnit.DAYS)
            val monthFilter = TimeRangeFilter.between(monthAgo, now)
            
            val sessions = healthConnectClient.readRecords(ReadRecordsRequest(ExerciseSessionRecord::class, monthFilter)).records
            Log.d("HealthConnectManager", "EXTREME DIAG: Found ${sessions.size} sessions in last 30d")
            
            val distances = healthConnectClient.readRecords(ReadRecordsRequest(DistanceRecord::class, monthFilter)).records
            Log.d("HealthConnectManager", "EXTREME DIAG: Found ${distances.size} distance records in last 30d")
            
            val calories = healthConnectClient.readRecords(ReadRecordsRequest(TotalCaloriesBurnedRecord::class, monthFilter)).records
            Log.d("HealthConnectManager", "EXTREME DIAG: Found ${calories.size} calorie records in last 30d")
            
            if (sessions.isNotEmpty()) {
                val types = sessions.map { it.exerciseType }.distinct()
                val sources = sessions.map { it.metadata.dataOrigin.packageName }.distinct()
                Log.d("HealthConnectManager", "EXTREME DIAG: Session types=$types, sources=$sources")
            }
        } catch (e: Exception) {
            Log.e("HealthConnectManager", "EXTREME DIAG FAILED: ${e.message}")
        }

        if (!hasForegroundPermissions()) {
            return FullActivityReport(0, 0.0, "Permission Denied", 0, false, 0, now)
        }

        val localDateTime = LocalDateTime.ofInstant(now, ZoneId.systemDefault())
        val startOfToday = localDateTime.toLocalDate().atStartOfDay(ZoneId.systemDefault()).toInstant()
        val queryStart = startOfToday
        val timeRangeFilter = TimeRangeFilter.between(queryStart, now)
        val fallbackStart = now.truncatedTo(ChronoUnit.HOURS)

        // 3. Read Exercise Sessions
        val sessions = healthConnectClient.readRecords(ReadRecordsRequest(ExerciseSessionRecord::class, timeRangeFilter)).records
        val walkingSessions = sessions.filter {
            it.exerciseType == ExerciseSessionRecord.EXERCISE_TYPE_WALKING
        }
        
        val effectiveStartTime = walkingSessions.minByOrNull { it.startTime }?.startTime ?: fallbackStart

        // 1. Read Steps
        val stepsRecords = healthConnectClient.readRecords(ReadRecordsRequest(StepsRecord::class, timeRangeFilter)).records
        val totalSteps = stepsRecords.sumOf { it.count }
        
        // 2. Read Distance
        val distanceRecords = healthConnectClient.readRecords(ReadRecordsRequest(DistanceRecord::class, timeRangeFilter)).records
        var totalDistanceMeters = distanceRecords.sumOf { it.distance.inMeters }
        
        var source = if (totalDistanceMeters > 0) "Health Connect (Distance)" else "Health Connect (Passive)"

        if (totalSteps > 0 && totalDistanceMeters == 0.0) {
            walkingSessions.forEach { session ->
                val sessionFilter = TimeRangeFilter.between(session.startTime, session.endTime)
                val sessionDist = healthConnectClient.readRecords(ReadRecordsRequest(DistanceRecord::class, sessionFilter)).records
                totalDistanceMeters += sessionDist.sumOf { it.distance.inMeters }
            }
        }

        // 4. Check for Routes
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

private data class FullActivityReport(
    val steps: Long,
    val distanceMeters: Double,
    val distanceSource: String,
    val walkingSessionsCount: Int,
    val hasExerciseRoutes: Boolean,
    val routePointCount: Int,
    val startTime: Instant
)
