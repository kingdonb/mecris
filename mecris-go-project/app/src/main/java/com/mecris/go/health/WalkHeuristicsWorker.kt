package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.mecris.go.auth.PocketIdAuth
import com.mecris.go.sync.SyncServiceApi
import com.mecris.go.sync.WalkDataSummaryDto
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class WalkHeuristicsWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    private val pocketIdAuth = PocketIdAuth(applicationContext)
    private val spinBaseUrl = "https://mecris-go-api-xupkwcis.fermyon.app/" 
    private val syncApi = SyncServiceApi.create(spinBaseUrl)
    
    private val prefs = applicationContext.getSharedPreferences("mecris_worker_state", Context.MODE_PRIVATE)

    override suspend fun doWork(): Result {
        val today = DateTimeFormatter.ISO_LOCAL_DATE.withZone(ZoneId.systemDefault()).format(Instant.now())
        
        // 1. Priority Lore: Backoff if already successful today
        val lastSyncedDay = prefs.getString("last_synced_day", "")
        if (lastSyncedDay == today) {
            Log.d("WalkHeuristicsWorker", "Priority Backoff: Walk already synced for $today. Skipping.")
            return Result.success()
        }

        Log.d("WalkHeuristicsWorker", "Executing background walk check for $today...")
        
        val healthManager = HealthConnectManager(applicationContext)
        
        // 2. Permission Check
        if (!healthManager.hasForegroundPermissions() || !healthManager.hasBackgroundPermission()) {
            Log.w("WalkHeuristicsWorker", "Missing permissions, cannot check health data in background.")
            return Result.failure()
        }

        try {
            val summary = healthManager.fetchRecentWalkData()
            Log.d("WalkHeuristicsWorker", "Health Data: Inferred=${summary.isWalkInferred}, Steps=${summary.totalSteps}")
            
            if (summary.isWalkInferred) {
                // 3. Reliable Token Retrieval
                val token = pocketIdAuth.getAccessTokenSuspend()
                if (token != null) {
                    val dto = WalkDataSummaryDto(
                        start_time = summary.startTime.toString(),
                        end_time = Instant.now().toString(),
                        step_count = summary.totalSteps.toInt(),
                        distance_meters = summary.totalDistanceMeters,
                        distance_source = summary.distanceSource,
                        confidence_score = 0.9,
                        gps_route_points = summary.routePointCount,
                        timezone = ZoneId.systemDefault().id
                    )

                    // 4. Awaitable Cloud Sync
                    val response = syncApi.uploadWalk("Bearer $token", dto)
                    Log.i("WalkHeuristicsWorker", "Cloud Sync SUCCESS: ${response.message}")
                    
                    // 5. Update Local State
                    prefs.edit().putString("last_synced_day", today).apply()
                } else {
                    Log.w("WalkHeuristicsWorker", "Auth required: Token retrieval failed.")
                    return Result.retry() // Retry later if auth was just a glitch
                }
            }
            
            return Result.success()
        } catch (e: Exception) {
            Log.e("WalkHeuristicsWorker", "Execution error: ${e.message}")
            return Result.retry()
        }
    }
}
