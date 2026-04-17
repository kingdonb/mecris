package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.mecris.go.auth.PocketIdAuth
import com.mecris.go.sync.SyncServiceApi
import com.mecris.go.sync.NagNotificationManager
import com.mecris.go.sync.ReviewPumpCalculator
import com.mecris.go.profile.ProfilePreferencesManager
import com.mecris.go.ai.SovereignBrain
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
    private val profileManager = ProfilePreferencesManager(applicationContext)
    private val brain = SovereignBrain(applicationContext)

    override suspend fun doWork(): Result {
        val originalTarget = inputData.getString("target_goal") ?: "ARABIC"
        Log.i("DelayedNagWorker", "Executing fuzzy nag check for: $originalTarget")

        val token = pocketIdAuth.getAccessTokenSuspend()
        val nagManager = NagNotificationManager(applicationContext)

        try {
            if (token != null) {
                // 1. RE-VERIFY: Fetch latest status from cloud
                val statusResponse = syncApi.getAggregateStatus("Bearer $token")
                if (statusResponse.isSuccessful) {
                    val status = statusResponse.body()
                    if (status != null) {
                        // 2. PIVOT: Decide what to nag about based on fresh data
                        val result = evaluateNagHierarchy(status, token)
                        if (result != null) {
                            val (title, message, prefKey, packageName, llmMessage) = result
                            
                            // Check cooldown again (just in case)
                            val lastNag = prefs.getLong(prefKey, 0L)
                            val fourHoursAgo = Instant.now().minusSeconds(14400).toEpochMilli()
                            
                            if (lastNag < fourHoursAgo) {
                                val finalMessage = llmMessage ?: message
                                Log.i("DelayedNagWorker", "Firing Nag: $title (LLM: ${llmMessage != null})")
                                nagManager.showNag(title, finalMessage, packageName)
                                prefs.edit().putLong(prefKey, Instant.now().toEpochMilli()).apply()
                            }
                        } else {
                            Log.i("DelayedNagWorker", "All clear or suppressed. No nag needed.")
                        }
                    }
                }
            } else {
                // 3. SOVEREIGN FALLBACK: Basic local walk check
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
        val localDateTime = java.time.LocalDateTime.now()
        val localHour = localDateTime.hour
        
        // --- Sensitivity Filter ---
        val isSensitive = status.vacation_mode_until?.let {
            try {
                val until = OffsetDateTime.parse(it).toInstant()
                now.isBefore(until)
            } catch (e: Exception) { false }
        } ?: false

        // 1. ARABIC (Priority 1: High Pressure)
        if (!status.components.arabic && localHour >= 8 && localHour < 20) {
            val llmNag = brain.generateNarrativeDirective("ARABIC", isSensitive, null)
            return NagResult(
                "ARABIC PRESSURE",
                "Your neural goal is in debt. Clear the cards. 📈",
                "last_arabic_nag_timestamp",
                "com.clozemaster.v2",
                llmNag
            )
        }

        // 2. WALK (Priority 2: Physical Wellbeing)
        if (!status.components.walk && localHour >= 8) {
            val weather = fetchWeatherOracle()
            if (weather != null) {
                if (!weather.is_dark && weather.is_walk_appropriate) {
                    val llmNag = brain.generateNarrativeDirective("WALK", isSensitive, weather.conditions, weather.is_dark)
                    val msg = if (isSensitive) "Time for a walk? Your physical goal is waiting. 🚶" 
                              else "Boris and Fiona are ready! 🐕 Time for a walk."
                    return NagResult("PHYSICAL GOAL", msg, "last_walk_nag_timestamp", "com.google.android.apps.fitness", llmNag)
                }
                if (weather.is_dark) {
                    Log.d("DelayedNagWorker", "It is dark. Giving up on walk, checking next priority.")
                }
            } else {
                if (localHour < 18) {
                    return NagResult("BORIS & FIONA 🐕", "Time for a walk?", "last_walk_nag_timestamp", "com.google.android.apps.fitness")
                }
            }
        }

        // 3. GREEK (Priority 3: Moussaka Final Boss)
        if (!status.components.greek) {
            val isMoussakaHour = localHour >= 17 && (localHour < 22 || (localHour == 22 && localDateTime.minute <= 30))
            val arabicCleared = status.components.arabic

            if (isMoussakaHour && (arabicCleared || localHour >= 20)) {
                val llmNag = brain.generateNarrativeDirective("GREEK", isSensitive, null)
                val msg = greekNagMessage(arabicCleared)
                return NagResult("GREEK ISLAND TIME 🏝️", msg, "last_greek_nag_timestamp", "com.clozemaster.v2", llmNag)
            }
        }

        return null
    }

    private suspend fun fetchWeatherOracle(): com.mecris.go.sync.WeatherHeuristicResponseDto? {
        val lat = profileManager.getLatitude()?.toDoubleOrNull() ?: 40.7128
        val lon = profileManager.getLongitude()?.toDoubleOrNull() ?: -74.0060
        return try {
            val resp = syncApi.getWeatherHeuristic(lat, lon)
            if (resp.isSuccessful) resp.body() else null
        } catch (e: Exception) { null }
    }

    data class NagResult(
        val title: String,
        val message: String,
        val prefKey: String,
        val packageName: String? = null,
        val llmMessage: String? = null
    )

    companion object {
        fun greekNagMessage(arabicCleared: Boolean): String {
            return if (arabicCleared) {
                "The moussaka is waiting! Spend a moment in Mykonos. 🇬🇷"
            } else {
                "The moussaka is waiting, but the cards come first. Spend a moment in Mykonos. 🇬🇷"
            }
        }
    }
}
