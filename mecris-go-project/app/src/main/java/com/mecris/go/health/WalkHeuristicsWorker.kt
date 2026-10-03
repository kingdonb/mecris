package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.mecris.go.auth.PocketIdAuthRepository
import com.mecris.go.sync.HeartbeatRequestDto
import com.mecris.go.sync.SyncServiceApi
import com.mecris.go.sync.WalkDataSummaryDto
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.concurrent.TimeUnit

import kotlin.jvm.JvmOverloads

class WalkHeuristicsWorker @JvmOverloads constructor(
    appContext: Context,
    workerParams: WorkerParameters,
    private val injectedAuth: PocketIdAuthRepository? = null,
    private val injectedSyncApi: SyncServiceApi? = null,
    private val etHourOverride: Int? = null
) : CoroutineWorker(appContext, workerParams) {

    private val pocketIdAuth = injectedAuth ?: PocketIdAuthRepository.getInstance(applicationContext)
    private val syncApi = injectedSyncApi ?: SyncServiceApi.create(com.mecris.go.BackendManager.getBaseUrl(applicationContext))
    
    private val prefs = applicationContext.getSharedPreferences("mecris_worker_state", Context.MODE_PRIVATE)

    override suspend fun doWork(): Result {
        val startedAt = System.currentTimeMillis()
        val phases = mutableListOf<String>()
        val result = runSync(phases)
        Log.i(
            "WalkHeuristicsWorker",
            "WORKER_METRIC run=walk_heuristics duration_ms=${System.currentTimeMillis() - startedAt} " +
                "phases=${phases.joinToString(",")} result=$result"
        )
        return result
    }

    private suspend fun runSync(phases: MutableList<String>): Result {
        val easternZone = ZoneId.of(WorkerPolicy.WORKER_TIMEZONE)
        val today = DateTimeFormatter.ISO_LOCAL_DATE.withZone(easternZone).format(Instant.now())
        val etHour = etHourOverride ?: WorkerPolicy.currentEtHour()
        
        // 1. Inertia Logic: Check if we already hit the "COMPLETED" state today
        val lastSyncedDay = prefs.getString("last_synced_day", "")
        val lastStepCount = prefs.getLong("last_step_count", 0L)
        val lastCloudSyncTrigger = prefs.getLong("last_cloud_sync_trigger", 0L)
        
        Log.d("WalkHeuristicsWorker", "Executing background check for $today (Last steps: $lastStepCount)")
        
        // 4. Proactive Token Refresh
        val token = pocketIdAuth.getAccessTokenSuspend().also { phases.add("auth") }

        // --- Heartbeat & Cooperation Phase ---
        try {
            if (token != null) {
                phases.add("hb")
                val hbResponse = syncApi.sendHeartbeat(
                    "Bearer $token",
                    com.mecris.go.sync.HeartbeatRequestDto(role = "android_client", process_id = "com.mecris.go")
                )
                
                if (hbResponse.isSuccessful) {
                    val body = hbResponse.body()
                    Log.i("WalkHeuristicsWorker", "Heartbeat SUCCESS. MCP Active: ${body?.mcp_server_active}")

                    // Task 588 Android hook: ask the backend for a Helix balance sync.
                    // The laptop leader polls helix_balance_requests and pushes the
                    // change-gated straight-copy datapoint to the helix-ml Beeminder goal.
                    // Battery diet (task 000622): at most one request per hour, waking
                    // hours only — the edge runs its upstream Helix fetch inline in
                    // this call, so every request also holds the phone radio up.
                    if (WorkerPolicy.shouldRequestHelixBalance(
                            prefs.getLong("last_helix_request", 0L),
                            Instant.now().toEpochMilli(),
                            etHour
                        )
                    ) {
                        phases.add("helix")
                        try {
                            val hlx = syncApi.requestHelixBalanceSync("Bearer $token")
                            if (hlx.isSuccessful) {
                                prefs.edit().putLong("last_helix_request", Instant.now().toEpochMilli()).apply()
                                Log.i("WalkHeuristicsWorker", "Helix balance sync requested; last known: ${hlx.body()?.last_balance ?: "none"} @ ${hlx.body()?.last_reading_ts ?: "n/a"}")
                            } else {
                                Log.w("WalkHeuristicsWorker", "Helix balance request code: ${hlx.code()}")
                            }
                        } catch (e: java.io.IOException) {
                            Log.d("WalkHeuristicsWorker", "Helix balance request skipped (offline): ${e.message}")
                        } catch (e: Exception) {
                            Log.e("WalkHeuristicsWorker", "Helix balance request failed: ${e.message}")
                        }
                    }

                    val twoHoursAgo = Instant.now().minusSeconds(7200).toEpochMilli()
                    if (body?.mcp_server_active == false && lastCloudSyncTrigger < twoHoursAgo) {
                        Log.w("WalkHeuristicsWorker", "MCP Server is DARK. Triggering Autonomous Cloud Sync + Reminders.")
                        phases.add("cloudsync")
                        val syncResponse = syncApi.triggerCloudSync("Bearer $token")
                        if (!syncResponse.isSuccessful) {
                            throw retrofit2.HttpException(syncResponse)
                        }
                        try {
                            val remindersResponse = syncApi.triggerReminders()
                            if (!remindersResponse.isSuccessful) {
                                Log.w("WalkHeuristicsWorker", "Reminders trigger returned: ${remindersResponse.code()}")
                            } else {
                                phases.add("reminders")
                            }
                        } catch (e: java.io.IOException) {
                            Log.d("WalkHeuristicsWorker", "Reminders trigger skipped (offline): ${e.message}")
                        } catch (e: Exception) {
                            Log.e("WalkHeuristicsWorker", "Reminders trigger failed: ${e.message}")
                        }
                        prefs.edit().putLong("last_cloud_sync_trigger", Instant.now().toEpochMilli()).apply()
                    }
                } else {
                    Log.w("WalkHeuristicsWorker", "Heartbeat failed with code: ${hbResponse.code()}")
                }
            }
        } catch (e: java.io.IOException) {
            Log.d("WalkHeuristicsWorker", "Cooperative check skipped (offline): ${e.message}")
        } catch (e: Exception) {
            Log.e("WalkHeuristicsWorker", "Cooperative check failed: ${e.message}")
        }

        // --- Arabic Pressure & Nag Phase (The Fuzzy Scheduler) ---
        // Battery diet (task 000622): debt evaluation only during waking hours; at
        // night the nag worker's own hour gates would suppress everything anyway.
        // The edge already folds pump + Beeminder due-today into aggregate-status
        // components (goal_met = pump_met AND due == 0), so the languages poll and
        // client-side pump math are gone — DelayedNagWorker re-evaluates the full
        // hierarchy from aggregate-status itself.
        if (!WorkerPolicy.isQuietHours(etHour)) {
            phases.add("nag_phase")
            try {
                if (token != null) {
                    phases.add("agg")
                    val aggregateResponse = syncApi.getAggregateStatus("Bearer $token")
                    val components = aggregateResponse.body()?.components

                    val debtGoals = components?.let {
                        listOfNotNull(
                            if (!it.arabic) "ARABIC" else null,
                            if (!it.walk) "WALK" else null,
                            if (!it.greek) "GREEK" else null
                        )
                    } ?: emptyList()

                    if (debtGoals.isNotEmpty()) {
                        val fuzzMinutes = (5..35).random().toLong()
                        Log.i("WalkHeuristicsWorker", "Goal debt detected (${debtGoals.joinToString("+")}). Scheduling fuzzy nag in $fuzzMinutes mins.")

                        val delayedRequest = OneTimeWorkRequestBuilder<DelayedNagWorker>()
                            .setInitialDelay(fuzzMinutes, java.util.concurrent.TimeUnit.MINUTES)
                            .setInputData(workDataOf("target_goal" to debtGoals.first()))
                            .build()

                        phases.add("nag_sched")
                        WorkManager.getInstance(applicationContext).enqueueUniqueWork(
                            "DelayedNagWork",
                            androidx.work.ExistingWorkPolicy.REPLACE,
                            delayedRequest
                        )
                    }
                }
            } catch (e: java.io.IOException) {
                Log.d("WalkHeuristicsWorker", "Nag scheduling skipped (offline): ${e.message}")
            } catch (e: Exception) {
                Log.e("WalkHeuristicsWorker", "Nag scheduling failed: ${e.message}")
            }
        }

        val healthManager = HealthConnectManager(applicationContext)
        phases.add("health")
        
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
                    phases.add("walk_upload")
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
        } catch (e: java.io.IOException) {
            Log.d("WalkHeuristicsWorker", "Health data cloud sync skipped (offline): ${e.message}")
            return Result.retry()
        } catch (e: Exception) {
            Log.e("WalkHeuristicsWorker", "Execution error: ${e.message}")
            return Result.retry()
        }
    }
}
