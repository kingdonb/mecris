package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.*
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.request.AggregateRequest
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

    // Level 2: High-sensitivity route permission (Corrected for Android 14+)
    val routePermission = HealthPermission.getReadPermission(ExerciseRouteRecord::class)

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

    private fun isPermissionGranted(granted: Set<String>, permission: String): Boolean {
        if (granted.contains(permission)) return true
        
        // Handle potential string mismatches between android.permission.health and androidx.health.permissions
        val altPermission = if (permission.startsWith("android.permission.health")) {
            permission.replace("android.permission.health.READ_", "androidx.health.permissions.read.")
        } else if (permission.startsWith("androidx.health.permissions.read")) {
            permission.replace("androidx.health.permissions.read.", "android.permission.health.READ_").uppercase()
        } else {
            null
        }
        
        return altPermission != null && granted.contains(altPermission)
    }

    suspend fun hasForegroundPermissions(): Boolean {
        if (!_isSupported.value) return false
        val granted = healthConnectClient.permissionController.getGrantedPermissions()
        Log.d("HealthConnectManager", "ALL GRANTED PERMS: $granted")
        
        val stepsPerm = HealthPermission.getReadPermission(StepsRecord::class)
        val distPerm = HealthPermission.getReadPermission(DistanceRecord::class)
        val exercisePerm = HealthPermission.getReadPermission(ExerciseSessionRecord::class)
        
        val stepsGranted = isPermissionGranted(granted, stepsPerm)
        val distGranted = isPermissionGranted(granted, distPerm)
        val exerciseGranted = isPermissionGranted(granted, exercisePerm)
        
        Log.d("HealthConnectManager", "CHECKING: steps=$stepsPerm ($stepsGranted), dist=$distPerm ($distGranted), exercise=$exercisePerm ($exerciseGranted)")
        return stepsGranted && distGranted && exerciseGranted
    }

    suspend fun hasRoutePermission(): Boolean {
        if (!_isSupported.value) return false
        val granted = healthConnectClient.permissionController.getGrantedPermissions()
        return isPermissionGranted(granted, routePermission)
    }

    suspend fun hasBackgroundPermission(): Boolean {
        if (!_isSupported.value) return false
        val granted = healthConnectClient.permissionController.getGrantedPermissions()
        return isPermissionGranted(granted, backgroundPermission)
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
            startTime = report.startTime,
            qualityReport = fetchDataQualityReport(report)
        )
    }

    private fun fetchDataQualityReport(report: FullActivityReport): DataQualityReport {
        val issues = mutableListOf<String>()
        
        // Check 1: Steps but no native distance (Fit "Track activity" might be off)
        if (report.steps > 500 && report.distanceSource.contains("Estimated")) {
            issues.add("Distance is estimated. Native distance recording might be disabled in source app.")
        }
        
        // Check 2: Sessions but no routes (Location might be off in source app)
        if (report.walkingSessionsCount > 0 && !report.hasExerciseRoutes) {
            issues.add("Exercise sessions found, but GPS routes are missing. Check location settings in source app.")
        }

        return DataQualityReport(
            isExcellent = issues.isEmpty() && report.hasExerciseRoutes && !report.distanceSource.contains("Estimated"),
            issues = issues,
            lastChecked = Instant.now()
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

        val localDateTime = LocalDateTime.ofInstant(now, ZoneId.of("America/New_York"))
        val startOfToday = localDateTime.toLocalDate().atStartOfDay(ZoneId.of("America/New_York")).toInstant()
        val queryStart = startOfToday
        val timeRangeFilter = TimeRangeFilter.between(queryStart, now)
        val fallbackStart = now.truncatedTo(ChronoUnit.HOURS)

        Log.d("HealthConnectManager", "Querying Health Connect from $queryStart to $now (Eastern Midnight)")

        // 1. Use Aggregate API for Steps and Distance (Native Deduplication)
        val aggregateRequest = AggregateRequest(
            metrics = setOf(StepsRecord.COUNT_TOTAL, DistanceRecord.DISTANCE_TOTAL),
            timeRangeFilter = timeRangeFilter
        )
        val aggregateResponse = healthConnectClient.aggregate(aggregateRequest)
        val totalSteps = aggregateResponse[StepsRecord.COUNT_TOTAL] ?: 0L
        val totalDistanceMeters = aggregateResponse[DistanceRecord.DISTANCE_TOTAL]?.inMeters ?: 0.0
        
        Log.d("HealthConnectManager", "Aggregate result: Steps=$totalSteps, Dist=$totalDistanceMeters")

        // 2. Read Sessions for metadata and routes
        val sessions = healthConnectClient.readRecords(ReadRecordsRequest(ExerciseSessionRecord::class, timeRangeFilter)).records
        val walkingSessions = sessions.filter {
            it.exerciseType == ExerciseSessionRecord.EXERCISE_TYPE_WALKING ||
            it.exerciseType == ExerciseSessionRecord.EXERCISE_TYPE_OTHER_WORKOUT ||
            it.exerciseType == 79 // Redundant but explicit for Issue #76
        }
        
        var source = if (totalDistanceMeters > 0) "Health Connect (Deduplicated)" else "Health Connect (Passive)"
        if (walkingSessions.isNotEmpty()) { source = "Health Connect (Workouts)" }

        // 3. Route Points and specific session diagnostics
        var hasRoutes = false
        var totalRoutePoints = 0
        walkingSessions.forEach { session ->
            Log.d("HealthConnectManager", "Inspecting session: ${session.metadata.id}, type=${session.exerciseType}, hasRoute=${session.exerciseRouteResult != null}")
            when (val routeResult = session.exerciseRouteResult) {
                is ExerciseRouteResult.Data -> {
                    hasRoutes = true
                    totalRoutePoints += routeResult.exerciseRoute.route.size
                    Log.d("HealthConnectManager", "SUCCESS: Found route with ${routeResult.exerciseRoute.route.size} pts for session ${session.metadata.id}")
                }
                is ExerciseRouteResult.NoData -> {
                    Log.d("HealthConnectManager", "ROUTE DIAG: Session ${session.metadata.id} has NO route data (NoData)")
                }
                is ExerciseRouteResult.ConsentRequired -> {
                    Log.w("HealthConnectManager", "ROUTE DIAG: Session ${session.metadata.id} requires CONSENT for routes!")
                }
                else -> {
                    Log.d("HealthConnectManager", "ROUTE DIAG: Session ${session.metadata.id} route result is unknown or null")
                }
            }
        }

        // 4. Final Fallback for missing distance (only if aggregate distance is truly zero)
        var finalDistance = totalDistanceMeters
        if (finalDistance == 0.0 && totalSteps > 0) {
            finalDistance = totalSteps * 0.66
            source = "Estimated from Steps (0.66m)"
        }

        val effectiveStartTime = walkingSessions.minByOrNull { it.startTime }?.startTime ?: fallbackStart

        return FullActivityReport(
            steps = totalSteps,
            distanceMeters = finalDistance,
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
    val startTime: Instant,
    val qualityReport: DataQualityReport = DataQualityReport(true, emptyList(), Instant.now())
)

data class DataQualityReport(
    val isExcellent: Boolean,
    val issues: List<String>,
    val lastChecked: Instant
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
