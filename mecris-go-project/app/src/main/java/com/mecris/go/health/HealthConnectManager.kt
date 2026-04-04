package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.core.content.ContextCompat
import android.content.pm.PackageManager
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

    // Level 2: High-sensitivity route permission
    // android.permission.health.READ_EXERCISE_ROUTES is the system permission string for Android 14+
    val routePermission = "android.permission.health.READ_EXERCISE_ROUTES"
    
    // The system requires READ_EXERCISE to be requested alongside READ_EXERCISE_ROUTES
    val routePermissionsArray = arrayOf(
        routePermission,
        HealthPermission.getReadPermission(ExerciseSessionRecord::class)
    )

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
        
        val stepsPerm = HealthPermission.getReadPermission(StepsRecord::class)
        val distPerm = HealthPermission.getReadPermission(DistanceRecord::class)
        val exercisePerm = HealthPermission.getReadPermission(ExerciseSessionRecord::class)
        
        return isPermissionGranted(granted, stepsPerm) && 
               isPermissionGranted(granted, distPerm) && 
               isPermissionGranted(granted, exercisePerm)
    }

    suspend fun hasRoutePermission(): Boolean {
        return ContextCompat.checkSelfPermission(context, routePermission) == PackageManager.PERMISSION_GRANTED
    }

    suspend fun hasBackgroundPermission(): Boolean {
        return ContextCompat.checkSelfPermission(context, backgroundPermission) == PackageManager.PERMISSION_GRANTED
    }

    suspend fun fetchRecentWalkData(): WalkDataSummary {
        val report = fetchFullActivityReport()
        val likelyWalked = report.steps >= 2000 || report.walkingSessionsCount > 0
        return WalkDataSummary(
            totalSteps = report.steps,
            totalDistanceMeters = report.distanceMeters,
            distanceSource = report.distanceSource,
            walkingSessionsCount = report.walkingSessionsCount,
            hasExerciseRoutes = report.hasExerciseRoutes,
            routePointCount = report.routePointCount,
            isWalkInferred = likelyWalked,
            startTime = report.startTime,
            consentableSessionId = report.consentableSessionId,
            qualityReport = fetchDataQualityReport(report)
        )
    }

    private fun fetchDataQualityReport(report: FullActivityReport): DataQualityReport {
        val issues = mutableListOf<String>()
        
        if (report.steps > 500 && report.distanceSource.contains("Estimated")) {
            issues.add("Distance is estimated. Native distance recording might be disabled in source app.")
        }

        return DataQualityReport(
            isExcellent = issues.isEmpty() && !report.distanceSource.contains("Estimated"),
            issues = issues,
            lastChecked = Instant.now()
        )
    }

    private suspend fun fetchFullActivityReport(): FullActivityReport {
        val now = Instant.now()
        val monthAgo = now.minus(30, ChronoUnit.DAYS)
        val monthFilter = TimeRangeFilter.between(monthAgo, now)
        
        try {
            val sessions = healthConnectClient.readRecords(ReadRecordsRequest(ExerciseSessionRecord::class, monthFilter)).records
            Log.d("HealthConnectManager", "DIAGNOSTIC: Found ${sessions.size} sessions in last 30d")
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (e: Exception) { 
            Log.e("HealthConnectManager", "Diag Failed: ${e.message}") 
        }

        if (!hasForegroundPermissions()) {
            return FullActivityReport(0, 0.0, "Permission Denied", 0, false, 0, now, null)
        }

        val localDateTime = LocalDateTime.ofInstant(now, ZoneId.of("America/New_York"))
        val startOfToday = localDateTime.toLocalDate().atStartOfDay(ZoneId.of("America/New_York")).toInstant()
        val queryStart = startOfToday
        val timeRangeFilter = TimeRangeFilter.between(queryStart, now)
        val fallbackStart = now.truncatedTo(ChronoUnit.HOURS)

        val aggregateRequest = AggregateRequest(
            metrics = setOf(StepsRecord.COUNT_TOTAL, DistanceRecord.DISTANCE_TOTAL),
            timeRangeFilter = timeRangeFilter
        )
        val aggregateResponse = healthConnectClient.aggregate(aggregateRequest)
        val totalSteps = aggregateResponse[StepsRecord.COUNT_TOTAL] ?: 0L
        val totalDistanceMeters = aggregateResponse[DistanceRecord.DISTANCE_TOTAL]?.inMeters ?: 0.0
        
        val sessions = healthConnectClient.readRecords(ReadRecordsRequest(ExerciseSessionRecord::class, timeRangeFilter)).records
        val walkingSessions = sessions.filter {
            it.exerciseType == ExerciseSessionRecord.EXERCISE_TYPE_WALKING ||
            it.exerciseType == ExerciseSessionRecord.EXERCISE_TYPE_OTHER_WORKOUT
        }
        
        var source = if (totalDistanceMeters > 0) "Health Connect (Deduplicated)" else "Health Connect (Passive)"
        if (walkingSessions.isNotEmpty()) { source = "Health Connect (Workouts)" }

        var hasRoutes = false
        var totalRoutePoints = 0
        var foundConsentableId: String? = null
        walkingSessions.forEach { session ->
            val routeResult = session.exerciseRouteResult
            Log.d("HealthConnectManager", "Inspecting session: ${session.metadata.id}, resultType=${routeResult::class.simpleName}")
            
            when (routeResult) {
                is ExerciseRouteResult.Data -> {
                    hasRoutes = true
                    totalRoutePoints += routeResult.exerciseRoute.route.size
                    Log.d("HealthConnectManager", "SUCCESS: Found route with ${routeResult.exerciseRoute.route.size} pts")
                }
                is ExerciseRouteResult.NoData -> {
                    Log.d("HealthConnectManager", "ROUTE DIAG: Session ${session.metadata.id} has NO route data (NoData)")
                }
                is ExerciseRouteResult.ConsentRequired -> {
                    Log.w("HealthConnectManager", "ROUTE DIAG: Session ${session.metadata.id} requires CONSENT for routes!")
                    if (foundConsentableId == null) foundConsentableId = session.metadata.id
                }
            }
        }

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
            startTime = effectiveStartTime,
            consentableSessionId = foundConsentableId
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
    val consentableSessionId: String?,
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
    val startTime: Instant,
    val consentableSessionId: String?
)
