package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.mecris.go.auth.PocketIdAuth
import com.mecris.go.sync.HeartbeatRequestDto
import com.mecris.go.sync.SyncServiceApi
import com.mecris.go.sync.WalkDataSummaryDto
import com.mecris.go.sync.NagNotificationManager
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

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
        val lastFailoverTrigger = prefs.getLong("last_failover_trigger", 0L)
        
        Log.d("WalkHeuristicsWorker", "Executing background check for $today (Last steps: $lastStepCount)")
        
        // 4. Reliable Token Retrieval
        val token = pocketIdAuth.getAccessTokenSuspend()

        // --- Heartbeat & Cooperation Phase (Agnostic of Health Permissions) ---
        try {
            if (token != null) {
                val hbResponse = syncApi.sendHeartbeat(
                    "Bearer $token",
                    com.mecris.go.sync.HeartbeatRequestDto(role = "android_client", process_id = "com.mecris.go")
                )
                
                if (hbResponse.isSuccessful) {
                    val body = hbResponse.body()
                    Log.i("WalkHeuristicsWorker", "Heartbeat SUCCESS. MCP Active: ${body?.mcp_server_active}")

                    // Cooperative Failover: If MCP is dark and we haven't triggered in 2 hours
                    val twoHoursAgo = Instant.now().minusSeconds(7200).toEpochMilli()
                    if (body?.mcp_server_active == false && lastFailoverTrigger < twoHoursAgo) {
                        Log.w("WalkHeuristicsWorker", "MCP Server is DARK. Triggering Autonomous Failover Sync.")
                        syncApi.triggerFailoverSync("Bearer $token")
                        prefs.edit().putLong("last_failover_trigger", Instant.now().toEpochMilli()).apply()
                    }
                } else {
                    Log.w("WalkHeuristicsWorker", "Heartbeat failed with code: ${hbResponse.code()}")
                }
            }
        } catch (e: Exception) {
            Log.e("WalkHeuristicsWorker", "Cooperative check failed: ${e.message}")
        }

        // --- Arabic Pressure & Nag Phase ---
        try {
            if (token != null) {
                val langResponse = syncApi.getLanguages("Bearer $token")
                
                if (langResponse.isSuccessful) {
                    val languages = langResponse.body()?.languages ?: emptyList()
                    
                    // 1. Arabic: High Pressure (PRIORITY)
                    val arabicStat = languages.find { it.name.equals("ARABIC", ignoreCase = true) }
                    var isArabicBehind = false
                    
                    if (arabicStat != null && arabicStat.current > 0) {
                        val multiplier = arabicStat.pump_multiplier ?: 1.0
                        val targetFlowRate = com.mecris.go.sync.ReviewPumpCalculator.calculateTargetFlowRate(
                            multiplier, arabicStat.current, arabicStat.tomorrow
                        )
                        
                        if (arabicStat.daily_completions < targetFlowRate) {
                            isArabicBehind = true
                            val lastNagTime = prefs.getLong("last_arabic_nag_timestamp", 0L)
                            val fourHoursAgo = Instant.now().minusSeconds(14400).toEpochMilli()
                            
                            if (lastNagTime < fourHoursAgo) {
                                Log.i("WalkHeuristicsWorker", "Triggering Arabic Pressure notification. Progress: ${arabicStat.daily_completions}/$targetFlowRate")
                                val nagManager = NagNotificationManager(applicationContext)
                                nagManager.showNag(
                                    title = "ARABIC PRESSURE",
                                    message = "Pace: ${arabicStat.daily_completions}/$targetFlowRate cards. Lever: ${multiplier}x. You are behind your neural goal. Clear the debt. 📈"
                                )
                                prefs.edit().putLong("last_arabic_nag_timestamp", Instant.now().toEpochMilli()).apply()
                            }
                        }
                    }

                    // 2. Greek: Island Time (Only if Arabic is cleared)
                    if (!isArabicBehind) {
                        val greekStat = languages.find { it.name.equals("GREEK", ignoreCase = true) }
                        if (greekStat != null && greekStat.current > 0) {
                            val multiplier = greekStat.pump_multiplier ?: 1.0
                            val targetFlowRate = com.mecris.go.sync.ReviewPumpCalculator.calculateTargetFlowRate(
                                multiplier, greekStat.current, greekStat.tomorrow
                            )
                            
                            if (greekStat.daily_completions < targetFlowRate) {
                                val lastNagTime = prefs.getLong("last_greek_nag_timestamp", 0L)
                                val fourHoursAgo = Instant.now().minusSeconds(14400).toEpochMilli()
                                
                                if (lastNagTime < fourHoursAgo) {
                                    Log.i("WalkHeuristicsWorker", "Triggering Greek Island Time notification. Progress: ${greekStat.daily_completions}/$targetFlowRate")
                                    val nagManager = NagNotificationManager(applicationContext)
                                    nagManager.showNag(
                                        title = "GREEK ISLAND TIME 🏝️",
                                        message = "Pace: ${greekStat.daily_completions}/$targetFlowRate points. The moussaka is waiting, but the cards come first. Spend a moment in Mykonos. 🇬🇷"
                                    )
                                    prefs.edit().putLong("last_greek_nag_timestamp", Instant.now().toEpochMilli()).apply()
                                }
                            }
                        }
                    } else {
                        Log.d("WalkHeuristicsWorker", "Arabic is behind. Suppressing Greek Island Time.")
                    }
                }
            }
        } catch (e: Exception) {
            Log.e("WalkHeuristicsWorker", "Nag check failed: ${e.message}")
        }

        val healthManager = HealthConnectManager(applicationContext)
        
        // 2. Permission Check
        if (!healthManager.hasForegroundPermissions() || !healthManager.hasBackgroundPermission()) {
            Log.w("WalkHeuristicsWorker", "Missing permissions, cannot check health data in background.")
            return Result.failure()
        }

        try {
            val summary = healthManager.fetchRecentWalkData()
            Log.d("WalkHeuristicsWorker", "Health Data: Inferred=${summary.isWalkInferred}, Steps=${summary.totalSteps}")
            
            // 3. Inertia Check: Only sync if status changed to 'inferred' or steps increased significantly
            val statusChanged = (lastSyncedDay != today && summary.isWalkInferred)
            val significantIncrease = (summary.totalSteps > lastStepCount + 500)
            
            if (statusChanged || significantIncrease) {
                // 4. Reliable Token Retrieval
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

                    // 5. Awaitable Cloud Sync
                    val syncResponse = syncApi.uploadWalk("Bearer $token", dto)
                    if (syncResponse.isSuccessful) {
                        Log.i("WalkHeuristicsWorker", "Cloud Sync SUCCESS: ${syncResponse.body()?.message}")
                        
                        // 6. Update Local State
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
