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
                        val healthManager = HealthConnectManager(applicationContext)
                        val summary = if (healthManager.hasForegroundPermissions()) healthManager.fetchRecentWalkData() else null
                        val result = evaluateNagHierarchy(status, token, summary)
                        if (result != null) {
                            val (title, message, prefKey, packageName, llmMessage) = result
                            
                            // Check cooldowns: 
                            // 1. Per-goal cooldown (prefKey)
                            // 2. Global cooldown (prevent 'machine gun' nagging)
                            val nowMs = Instant.now().toEpochMilli()
                            
                            // Default cooldown is 4 hours (14,400,000 ms)
                            var cooldownMs = 14400000L
                            
                            // Moussaka Exception: If we are nagging about Greek, allow a tighter 1.5h window (5,400,000 ms)
                            // This ensures that if Arabic and Walk are done, the Greek nag can fire sooner during 'Moussaka Hour'.
                            if (prefKey == "last_greek_nag_timestamp") {
                                cooldownMs = 5400000L 
                                Log.i("DelayedNagWorker", "Moussaka Exception: Reducing cooldown to 1.5h for Greek nag")
                            }

                            val lastGoalNag = prefs.getLong(prefKey, 0L)
                            val lastGlobalNag = prefs.getLong("global_last_nag_timestamp", 0L)
                            
                            if (lastGoalNag < (nowMs - cooldownMs) && lastGlobalNag < (nowMs - cooldownMs)) {
                                val finalMessage = llmMessage ?: message
                                Log.i("DelayedNagWorker", "Firing Nag: $title (LLM: ${llmMessage != null})")
                                nagManager.showNag(title, finalMessage, packageName)
                                
                                // Update both timestamps
                                prefs.edit()
                                    .putLong(prefKey, nowMs)
                                    .putLong("global_last_nag_timestamp", nowMs)
                                    .apply()
                            } else {
                                Log.i("DelayedNagWorker", "Nag suppressed by cooldown ($prefKey: ${nowMs - lastGoalNag}ms age, Global: ${nowMs - lastGlobalNag}ms age, Target: ${cooldownMs}ms)")
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
                        // CHECK COOLDOWN even for fallback nags
                        val nowMs = Instant.now().toEpochMilli()
                        val fourHoursAgoMs = nowMs - 14400000L
                        val lastGlobalNag = prefs.getLong("global_last_nag_timestamp", 0L)
                        
                        if (lastGlobalNag < fourHoursAgoMs) {
                            val hasPartialWalk = summary.walkingSessionsCount > 0 || summary.totalDistanceMeters > 0.0
                            val fallbackTitle = if (hasPartialWalk) "MAJESTY CAKE 🍰" else "BORIS & FIONA \uD83D\uDC15"
                            val fallbackMsg = if (hasPartialWalk) "You logged a walk, but the Majesty Cake requires 2000 steps! Go get that cake. 🍰" else "Time for a walk? Your steps are low today."
                            
                            Log.i("DelayedNagWorker", "Firing Sovereign Fallback Nag: $fallbackTitle")
                            nagManager.showNag(fallbackTitle, fallbackMsg, "com.google.android.apps.fitness")
                            
                            prefs.edit()
                                .putLong("global_last_nag_timestamp", nowMs)
                                .apply()
                        } else {
                            Log.i("DelayedNagWorker", "Sovereign Fallback suppressed by global cooldown")
                        }
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
        token: String,
        walkSummary: WalkDataSummary?
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

        // 2. WALK / MAJESTY CAKE (Priority 2: Physical Wellbeing)
        if (!status.components.walk && localHour >= 8) {
            val hasPartialWalk = walkSummary != null && (walkSummary.walkingSessionsCount > 0 || walkSummary.totalDistanceMeters > 0.0) && walkSummary.totalSteps < 2000
            val goalName = if (hasPartialWalk) "MAJESTY CAKE" else "WALK"
            val fallbackTitle = if (hasPartialWalk) "MAJESTY CAKE 🍰" else "PHYSICAL GOAL"
            val fallbackMsgSensitive = if (hasPartialWalk) "You logged a walk, but the Majesty Cake requires 2000 steps! Go get that cake. 🍰" else "Time for a walk? Your physical goal is waiting. 🚶"
            val fallbackMsgNormal = if (hasPartialWalk) "You logged a walk, but the Majesty Cake requires 2000 steps! Go get that cake. 🍰" else "Boris and Fiona are ready! 🐕 Time for a walk."
            
            val weather = fetchWeatherOracle()
            if (weather != null) {
                if (!weather.is_dark && weather.is_walk_appropriate) {
                    val llmNag = brain.generateNarrativeDirective(goalName, isSensitive, weather.conditions, weather.is_dark)
                    val msg = if (isSensitive) fallbackMsgSensitive else fallbackMsgNormal
                    return NagResult(fallbackTitle, msg, "last_walk_nag_timestamp", "com.google.android.apps.fitness", llmNag)
                }
                if (weather.is_dark) {
                    Log.d("DelayedNagWorker", "It is dark. Giving up on walk/cake, checking next priority.")
                }
            } else {
                if (localHour < 18) {
                    return NagResult(fallbackTitle, if (isSensitive) fallbackMsgSensitive else fallbackMsgNormal, "last_walk_nag_timestamp", "com.google.android.apps.fitness")
                }
            }
        }

        // 3. GREEK (Priority 3: Moussaka Final Boss)
        if (!status.components.greek) {
            val isMoussakaHour = localHour >= 17 && (localHour < 22 || (localHour == 22 && localDateTime.minute <= 30))
            val arabicCleared = status.components.arabic

            if (isMoussakaHour && (arabicCleared || localHour >= 20)) {
                val llmNag = brain.generateNarrativeDirective("GREEK", isSensitive, null)
                val msg = greekNagMessage(arabicCleared, isArabicHour = localHour < 20)
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
        fun greekNagMessage(arabicCleared: Boolean, isArabicHour: Boolean = true): String {
            return if (arabicCleared || !isArabicHour) {
                "The moussaka is waiting! Spend a moment in Mykonos. 🇬🇷"
            } else {
                "The moussaka is waiting, but the cards come first. Spend a moment in Mykonos. 🇬🇷"
            }
        }
    }
}
