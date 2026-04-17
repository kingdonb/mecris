package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.mecris.go.auth.PocketIdAuth
import com.mecris.go.sync.SyncServiceApi
import com.mecris.go.sync.NagNotificationManager
import com.mecris.go.sync.ReviewPumpCalculator
import java.time.Instant
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter

class DelayedNagWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    private val pocketIdAuth = PocketIdAuth(applicationContext)
    private val spinBaseUrl = "https://mecris-sync-v2-r0r86pso.fermyon.app/"
    private val syncApi = SyncServiceApi.create(spinBaseUrl)
    private val prefs = applicationContext.getSharedPreferences("mecris_worker_state", Context.MODE_PRIVATE)

    override suspend fun doWork(): Result {
        val originalTarget = inputData.getString("target_goal") ?: "ARABIC"
        Log.i("DelayedNagWorker", "Executing fuzzy nag check for: $originalTarget")

        val token = pocketIdAuth.getAccessTokenSuspend()
        val nagManager = NagNotificationManager(applicationContext)

        try {
            if (token != null) {
                val statusResponse = syncApi.getAggregateStatus("Bearer $token")
                if (statusResponse.isSuccessful) {
                    val status = statusResponse.body()
                    if (status != null) {
                        val result = evaluateNagHierarchy(status, token)
                        if (result != null) {
                            val (title, message, prefKey, packageName) = result
                            
                            val lastNag = prefs.getLong(prefKey, 0L)
                            val fourHoursAgo = Instant.now().minusSeconds(14400).toEpochMilli()
                            
                            if (lastNag < fourHoursAgo) {
                                Log.i("DelayedNagWorker", "Firing Nag: $title")
                                nagManager.showNag(title, message, packageName)
                                prefs.edit().putLong(prefKey, Instant.now().toEpochMilli()).apply()
                            }
                        } else {
                            Log.i("DelayedNagWorker", "All clear or suppressed. No nag needed.")
                        }
                    }
                }
            } else {
                val healthManager = HealthConnectManager(applicationContext)
                if (healthManager.hasForegroundPermissions()) {
                    val summary = healthManager.fetchRecentWalkData()
                    if (summary.totalSteps < 2000) {
                        nagManager.showNag("BORIS & FIONA 🐕", "Time for a sovereign walk? Your steps are low.", "com.google.android.apps.fitness")
                    }
                }
            }
            return Result.success()
        } catch (e: Exception) {
            Log.e("DelayedNagWorker", "Failed to execute nag: ${e.message}")
            return Result.failure()
        }
    }

    private suspend fun evaluateNagHierarchy(
        status: com.mecris.go.sync.AggregateStatusResponseDto,
        token: String
    ): NagResult? {
        val now = Instant.now()
        
        val isSensitive = status.vacation_mode_until?.let {
            try {
                val until = OffsetDateTime.parse(it).toInstant()
                now.isBefore(until)
            } catch (e: Exception) { false }
        } ?: false

        if (!status.components.arabic) {
            return NagResult(
                "ARABIC PRESSURE",
                "Your neural goal is in debt. Clear the cards. 📈",
                "last_arabic_nag_timestamp",
                "com.clozemaster.v2"
            )
        }

        if (!status.components.walk) {
            val weather = fetchWeatherOracle()
            if (weather != null && !weather.is_dark && weather.is_walk_appropriate) {
                val msg = if (isSensitive) "Time for a walk? Your physical goal is waiting. 🚶" 
                          else "Boris and Fiona are ready! 🐕 Time for a walk."
                return NagResult("PHYSICAL GOAL", msg, "last_walk_nag_timestamp", "com.google.android.apps.fitness")
            }
        }

        if (!status.components.greek) {
            val localHour = java.time.LocalDateTime.now().hour
            if (localHour >= 17 && localHour <= 22) {
                val msg = "The moussaka is waiting, but the cards come first. Spend a moment in Mykonos. 🇬🇷"
                return NagResult("GREEK ISLAND TIME 🏝️", msg, "last_greek_nag_timestamp", "com.clozemaster.v2")
            }
        }

        return null
    }

    private suspend fun fetchWeatherOracle(): com.mecris.go.sync.WeatherHeuristicResponseDto? {
        return try {
            val resp = syncApi.getWeatherHeuristic(40.7128, -74.0060)
            if (resp.isSuccessful) resp.body() else null
        } catch (e: Exception) { null }
    }

    data class NagResult(val title: String, val message: String, val prefKey: String, val packageName: String? = null)
}
