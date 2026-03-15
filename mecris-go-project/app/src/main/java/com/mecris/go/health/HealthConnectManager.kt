package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.DistanceRecord
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.ExerciseRouteResult
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
        
        // Detailed logging of permissions for diagnostics
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
        
        // 0. Deep Diagnostic: Scan last 7 days for ANY exercise sessions
        try {
            val weekAgo = now.minus(7, ChronoUnit.DAYS)
            val weekFilter = TimeRangeFilter.between(weekAgo, now)
            
            val weekSessions = healthConnectClient.readRecords(ReadRecordsRequest(ExerciseSessionRecord::class, weekFilter)).records
            Log.d("HealthConnectManager", "DIAGNOSTIC: Found ${weekSessions.size} sessions in last 7d")
            weekSessions.forEach { 
                Log.d("HealthConnectManager", "DIAGNOSTIC SESSION: ID=${it.metadata.id}, Type=${it.exerciseType}, Start=${it.startTime}, Source=${it.metadata.dataOrigin.packageName}")
            }

            // Diagnostic: Broad Distance Scan
            val weekDistRecords = healthConnectClient.readRecords(ReadRecordsRequest(DistanceRecord::class, weekFilter)).records
            Log.d("HealthConnectManager", "DIAGNOSTIC: Found ${weekDistRecords.size} distance records in last 7d")
            if (weekDistRecords.isNotEmpty()) {
                val totalDist = weekDistRecords.sumOf { it.distance.inMeters }
                Log.d("HealthConnectManager", "DIAGNOSTIC: Total distance in last 7d: $totalDist meters")
            }
        } catch (e: Exception) {
            Log.e("HealthConnectManager", "DIAGNOSTIC FAILED: ${e.message}")
        }

        if (!hasForegroundPermissions()) {
            Log.w("HealthConnectManager", "Missing core permissions")
            return FullActivityReport(0, 0.0, "Permission Denied", 0, false, 0, now)
        }

        val localDateTime = LocalDateTime.ofInstant(now, ZoneId.systemDefault())
        val startOfToday = localDateTime.toLocalDate().atStartOfDay(ZoneId.systemDefault()).toInstant()
        val queryStart = startOfToday
        val timeRangeFilter = TimeRangeFilter.between(queryStart, now)
        val fallbackStart = now.truncatedTo(ChronoUnit.HOURS)

        Log.d("HealthConnectManager", "Querying Health Connect from $queryStart to $now")

        // 3. Read Exercise Sessions
        val sessions = healthConnectClient.readRecords(ReadRecordsRequest(ExerciseSessionRecord::class, timeRangeFilter)).records
        val walkingSessions = sessions.filter {
            it.exerciseType == ExerciseSessionRecord.EXERCISE_TYPE_WALKING
        }
        Log.d("HealthConnectManager", "Walking sessions found today: ${walkingSessions.size}")
        
        val effectiveStartTime = walkingSessions.minByOrNull { it.startTime }?.startTime ?: fallbackStart

        // 1. Read Steps
        val stepsRecords = healthConnectClient.readRecords(ReadRecordsRequest(StepsRecord::class, timeRangeFilter)).records
        val totalSteps = stepsRecords.sumOf { it.count }
        Log.d("HealthConnectManager", "Steps from generic query: $totalSteps")
        if (stepsRecords.isNotEmpty()) {
            val sources = stepsRecords.map { it.metadata.dataOrigin.packageName }.distinct()
            Log.d("HealthConnectManager", "Steps source apps: $sources")
        }

        // 2. Read Distance
        val distanceRecords = healthConnectClient.readRecords(ReadRecordsRequest(DistanceRecord::class, timeRangeFilter)).records
        var totalDistanceMeters = distanceRecords.sumOf { it.distance.inMeters }
        Log.d("HealthConnectManager", "Distance from generic query: $totalDistanceMeters")
        
        var source = if (totalDistanceMeters > 0) "Health Connect (Distance)" else "Health Connect (Passive)"

        if (totalSteps > 0 && totalDistanceMeters == 0.0) {
            Log.d("HealthConnectManager", "Attempting session-specific distance fallback")
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
                    Log.d("HealthConnectManager", "Found route with ${routeResult.exerciseRoute.route.size} pts")
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

private data class FullActivityReport(
    val steps: Long,
    val distanceMeters: Double,
    val distanceSource: String,
    val walkingSessionsCount: Int,
    val hasExerciseRoutes: Boolean,
    val routePointCount: Int,
    val startTime: Instant
)
