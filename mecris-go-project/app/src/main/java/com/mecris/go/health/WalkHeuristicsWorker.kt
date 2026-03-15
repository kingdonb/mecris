package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.mecris.go.auth.PocketIdAuth
import com.mecris.go.sync.SyncServiceApi
import com.mecris.go.sync.WalkDataSummaryDto
import kotlinx.coroutines.DelicateCoroutinesApi
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId

class WalkHeuristicsWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    // Note: In a real production app, we would use Dependency Injection (Dagger/Hilt)
    // For this Phase 2 vertical slice, we instantiate manually.
    private val pocketIdAuth = PocketIdAuth(applicationContext)
    private val spinBaseUrl = "https://mecris-go-api-xupkwcis.fermyon.app/" 
    private val syncApi = SyncServiceApi.create(spinBaseUrl)

    @OptIn(DelicateCoroutinesApi::class)
    override suspend fun doWork(): Result {
        Log.d("WalkHeuristicsWorker", "Running background walk check...")
        
        val healthManager = HealthConnectManager(applicationContext)
        
        if (!healthManager.hasForegroundPermissions() || !healthManager.hasBackgroundPermission()) {
            Log.e("WalkHeuristicsWorker", "Missing required Health Connect permissions")
            return Result.failure()
        }

        try {
            val summary = healthManager.fetchRecentWalkData()
            Log.d("WalkHeuristicsWorker", "Walk Inferred: ${summary.isWalkInferred} (Steps: ${summary.totalSteps})")
            
            if (summary.isWalkInferred) {
                // Background Sync Logic
                pocketIdAuth.getValidAccessToken { token ->
                    if (token != null) {
                        // We have a token, perform sync
                        // Using GlobalScope for the callback fire-and-forget in background worker
                        GlobalScope.launch { 
                            try {
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
                                syncApi.uploadWalk("Bearer $token", dto)
                                Log.i("WalkHeuristicsWorker", "Background sync successful")
                            } catch (e: Exception) {
                                Log.e("WalkHeuristicsWorker", "Background sync failed", e)
                            }
                        }
                    } else {
                        Log.w("WalkHeuristicsWorker", "No token available, skipping background sync")
                    }
                }

                // Keep local cache for UI
                val prefs = applicationContext.getSharedPreferences("mecris_go_prefs", Context.MODE_PRIVATE)
                prefs.edit().putBoolean("walk_inferred_today", true).apply()
            }
            
            return Result.success()
        } catch (e: Exception) {
            Log.e("WalkHeuristicsWorker", "Error fetching health data", e)
            return Result.retry()
        }
    }
}
