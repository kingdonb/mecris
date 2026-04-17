package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.mecris.go.auth.PocketIdAuth
import com.mecris.go.sync.HeartbeatRequestDto
import com.mecris.go.sync.SyncServiceApi
import com.mecris.go.sync.WalkDataSummaryDto
import com.mecris.go.sync.NagNotificationManager
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.concurrent.TimeUnit

import kotlin.jvm.JvmOverloads

class WalkHeuristicsWorker @JvmOverloads constructor(
    appContext: Context,
    workerParams: WorkerParameters,
    private val injectedAuth: PocketIdAuth? = null,
    private val injectedSyncApi: SyncServiceApi? = null
) : CoroutineWorker(appContext, workerParams) {

    private val pocketIdAuth = injectedAuth ?: PocketIdAuth(applicationContext)
    private val spinBaseUrl = "https://mecris-sync-v2-r0r86pso.fermyon.app/" 
    private val syncApi = injectedSyncApi ?: SyncServiceApi.create(spinBaseUrl)
    
    private val prefs = applicationContext.getSharedPreferences("mecris_worker_state", Context.MODE_PRIVATE)

    override suspend fun doWork(): Result {
        val easternZone = ZoneId.of("America/New_York")
        val today = DateTimeFormatter.ISO_LOCAL_DATE.withZone(easternZone).format(Instant.now())
        
        // 1. Inertia Logic: Check if we already hit the "COMPLETED" state today
        val lastSyncedDay = prefs.getString("last_synced_day", "")
        val lastStepCount = prefs.getLong("last_step_count", 0L)
        val lastCloudSyncTrigger = prefs.getLong("last_cloud_sync_trigger", 0L)
        
        Log.d("WalkHeuristicsWorker", "Executing background check for $today (Last steps: $lastStepCount)")
        
        // 4. Proactive Token Refresh
        val token = pocketIdAuth.getAccessTokenSuspend()

        // --- Heartbeat & Cooperation Phase ---
        try {
            if (token != null) {
                val hbResponse = syncApi.sendHeartbeat(
                    "Bearer $token",
                    com.mecris.go.sync.HeartbeatRequestDto(role = "android_client", process_id = "com.mecris.go")
                )
                
                if (hbResponse.isSuccessful) {
                    val body = hbResponse.body()
                    Log.i("WalkHeuristicsWorker", "Heartbeat SUCCESS. MCP Active: ${body?.mcp_server_active}")

                    val twoHoursAgo = Instant.now().minusSeconds(7200).toEpochMilli()
                    if (body?.mcp_server_active == false && lastCloudSyncTrigger < twoHoursAgo) {
                        Log.w("WalkHeuristicsWorker", "MCP Server is DARK. Triggering Autonomous Cloud Sync + Reminders.")
                        val syncResponse = syncApi.triggerCloudSync("Bearer $token")
                        if (!syncResponse.isSuccessful) {
                            throw retrofit2.HttpException(syncResponse)
                        }
                        try {
                            val remindersResponse = syncApi.triggerReminders()
                            if (!remindersResponse.isSuccessful) {
                                Log.w("WalkHeuristicsWorker", "Reminders trigger returned: ${remindersResponse.code()}")
                            }
                        } catch (e: Exception) {
                            Log.e("WalkHeuristicsWorker", "Reminders trigger failed: ${e.message}")
                        }
                        prefs.edit().putLong("last_cloud_sync_trigger", Instant.now().toEpochMilli()).apply()
                    }
                } else {
                    Log.w("WalkHeuristicsWorker", "Heartbeat failed with code: ${hbResponse.code()}")
                }
            }
        } catch (e: Exception) {
            Log.e("WalkHeuristicsWorker", "Cooperative check failed: ${e.message}")
        }

        // --- Arabic Pressure & Nag Phase (The Fuzzy Scheduler) ---
        try {
            if (token != null) {
                val langResponse = syncApi.getLanguages("Bearer $token")
                
                if (langResponse.isSuccessful) {
                    val languages = langResponse.body()?.languages ?: emptyList()
                    val aggregateResponse = syncApi.getAggregateStatus("Bearer $token")
                    val aggregate = aggregateResponse.body()

                    // Check if any goal is in debt
                    val arabicStat = languages.find { it.name.equals("ARABIC", ignoreCase = true) }
                    val greekStat = languages.find { it.name.equals("GREEK", ignoreCase = true) }
                    
                    var targetGoal: String? = null
                    
                    if (arabicStat != null && arabicStat.current > 0) {
                        val target = com.mecris.go.sync.ReviewPumpCalculator.calculateTargetFlowRate(
                            arabicStat.pump_multiplier ?: 1.0, arabicStat.current, arabicStat.tomorrow
                        )
                        if (arabicStat.daily_completions < target) targetGoal = "ARABIC"
                    }
                    
                    if (targetGoal == null && aggregate?.components?.walk == false) {
                        targetGoal = "WALK"
                    }

                    if (targetGoal == null && greekStat != null && greekStat.current > 0) {
                        val target = com.mecris.go.sync.ReviewPumpCalculator.calculateTargetFlowRate(
                            greekStat.pump_multiplier ?: 1.0, greekStat.current, greekStat.tomorrow
                        )
                        if (greekStat.daily_completions < target) targetGoal = "GREEK"
                    }

                    if (targetGoal != null) {
                        val fuzzMinutes = (5..35).random().toLong()
                        Log.i("WalkHeuristicsWorker", "Goal debt detected ($targetGoal). Scheduling fuzzy nag in $fuzzMinutes mins.")

                        val delayedRequest = OneTimeWorkRequestBuilder<DelayedNagWorker>()
                            .setInitialDelay(fuzzMinutes, java.util.concurrent.TimeUnit.MINUTES)
                            .setInputData(workDataOf("target_goal" to targetGoal))
                            .build()

                        WorkManager.getInstance(applicationContext).enqueueUniqueWork(
                            "DelayedNagWork",
                            androidx.work.ExistingWorkPolicy.REPLACE,
                            delayedRequest
                        )
                    }
                }
            }
        } catch (e: Exception) {
            Log.e("WalkHeuristicsWorker", "Nag scheduling failed: ${e.message}")
        }

        val healthManager = HealthConnectManager(applicationContext)
        
        if (!healthManager.hasForegroundPermissions() || !healthManager.hasBackgroundPermission()) {
            Log.w("WalkHeuristicsWorker", "Missing permissions, cannot check health data in background.")
            return Result.failure()
        }

        try {
            val summary = healthManager.fetchRecentWalkData()
            Log.d("WalkHeuristicsWorker", "Health Data: Inferred=${summary.isWalkInferred}, Steps=${summary.totalSteps}")
            
            val statusChanged = (lastSyncedDay != today && summary.isWalkInferred)
            val significantIncrease = (summary.totalSteps > lastStepCount + 500)
            
            if (statusChanged || significantIncrease) {
                if (token != null) {
                    val dto = WalkDataSummaryDto(
                        start_time = summary.startTime.toString(),
                        end_time = Instant.now().toString(),
                        step_count = summary.totalSteps.toInt(),
                        distance_meters = summary.totalDistanceMeters,
                        distance_source = summary.distanceSource,
                        confidence_score = if (summary.isWalkInferred) 0.9 else 0.1,
                        gps_route_points = summary.routePointCount,
                        timezone = ZoneId.of("America/New_York").id
                    )

                    val syncResponse = syncApi.uploadWalk("Bearer $token", dto)
                    if (syncResponse.isSuccessful) {
                        Log.i("WalkHeuristicsWorker", "Cloud Sync SUCCESS: ${syncResponse.body()?.message}")
                        
                        prefs.edit()
                            .putString("last_synced_day", if (summary.isWalkInferred) today else lastSyncedDay)
                            .putLong("last_step_count", summary.totalSteps)
                            .apply()
                    } else {
                        Log.e("WalkHeuristicsWorker", "Cloud Sync FAILED: ${syncResponse.code()}")
                    }
                } else {
                    Log.w("WalkHeuristicsWorker", "Auth required: Token retrieval failed.")
                    return Result.retry() 
                }
            } else {
                Log.d("WalkHeuristicsWorker", "Inertia Backoff: No significant change since last sync.")
            }
            
            return Result.success()
        } catch (e: Exception) {
            Log.e("WalkHeuristicsWorker", "Execution error: ${e.message}")
            return Result.retry()
        }
    }
}
