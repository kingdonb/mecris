package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.mecris.go.auth.PocketIdAuthRepository
import com.mecris.go.sync.SyncServiceApi
import com.mecris.go.sync.NagNotificationManager
import com.mecris.go.sync.AggregateStatusResponseDto
import com.mecris.go.sync.WeatherHeuristicResponseDto
import com.mecris.go.profile.ProfilePreferencesManager
import com.mecris.go.ai.SovereignBrain
import java.time.Instant
import java.time.OffsetDateTime

class DelayedNagWorker @JvmOverloads constructor(
    appContext: Context,
    workerParams: WorkerParameters,
    private val injectedAuth: PocketIdAuthRepository? = null,
    private val injectedSyncApi: SyncServiceApi? = null,
    private val injectedBrain: SovereignBrain? = null,
    private val injectedNagManager: NagNotificationManager? = null,
    private val injectedHour: Int? = null
) : CoroutineWorker(appContext, workerParams) {

    private val pocketIdAuth = injectedAuth ?: PocketIdAuthRepository.getInstance(applicationContext)
    private val syncApi = injectedSyncApi ?: SyncServiceApi.create(com.mecris.go.BackendManager.getBaseUrl(applicationContext))
    private val prefs = applicationContext.getSharedPreferences("mecris_worker_state", Context.MODE_PRIVATE)
    private val profileManager = ProfilePreferencesManager(applicationContext)
    private val brain = injectedBrain ?: SovereignBrain(applicationContext)

    override suspend fun doWork(): Result {
        val startedAt = System.currentTimeMillis()
        val phases = mutableListOf<String>()
        val originalTarget = inputData.getString("target_goal") ?: "ARABIC"
        Log.i("DelayedNagWorker", "Executing fuzzy nag check for: $originalTarget")

        val result = runNagCheck(phases)
        Log.i(
            "DelayedNagWorker",
            "WORKER_METRIC run=delayed_nag duration_ms=${System.currentTimeMillis() - startedAt} " +
                "phases=${phases.joinToString(",")} result=$result"
        )
        return result
    }

    private suspend fun runNagCheck(phases: MutableList<String>): Result {
        val token = pocketIdAuth.getAccessTokenSuspend()
        val nagManager = injectedNagManager ?: NagNotificationManager(applicationContext, syncApi)

        try {
            var status: AggregateStatusResponseDto? = null
            if (token != null) {
                try {
                    phases.add("agg")
                    val statusResponse = syncApi.getAggregateStatus("Bearer $token")
                    if (statusResponse.isSuccessful) {
                        status = statusResponse.body()
                    }
                } catch (e: java.io.IOException) {
                    Log.d("DelayedNagWorker", "Cloud aggregate status unreachable (offline): ${e.message}")
                }
            }

            if (status != null) {
                // 2. PIVOT: battery-diet reorder (task 000622). Pick the nag target from
                // cheap data (aggregate components + hour gates), consult the
                // SharedPreferences cooldowns, and only then spend weather fetches,
                // Health Connect reads, or on-device LLM inference. Firing behavior
                // (hierarchy, cooldowns, messages) matches the old evaluateNagHierarchy;
                // only the wasted pre-cooldown work is gone.
                val isSensitive = isSensitiveMode(status)
                val localNow = java.time.LocalDateTime.now()
                val hour = injectedHour ?: localNow.hour
                val minute = localNow.minute

                val intent = evaluateNagIntent(
                    status.components.arabic,
                    status.components.walk,
                    status.components.greek,
                    hour,
                    minute
                )

                if (intent == null) {
                    Log.i("DelayedNagWorker", "All clear or outside nag windows. No nag needed.")
                    return Result.success()
                }

                // Walk decisions need the weather oracle (dark / unsuitable → fall
                // through to Greek); skip the fetch when cooldown already rules out
                // both candidates.
                var finalIntent = intent
                var weather: WeatherHeuristicResponseDto? = null
                if (intent.goal == GOAL_WALK) {
                    if (!isCooldownCleared(intent.prefKey, intent.cooldownMs) && !intent.greekEligible) {
                        Log.i("DelayedNagWorker", "Nag suppressed by cooldown (${intent.prefKey}); skipping weather/LLM.")
                        return Result.success()
                    }
                    phases.add("weather")
                    weather = fetchWeatherOracle()
                    finalIntent = resolveWalkIntent(intent, weather, hour)
                    if (finalIntent == null) {
                        Log.i("DelayedNagWorker", "Walk nag dropped by weather. No nag needed.")
                        return Result.success()
                    }
                }

                if (!isCooldownCleared(finalIntent.prefKey, finalIntent.cooldownMs)) {
                    Log.i("DelayedNagWorker", "Nag suppressed by cooldown (${finalIntent.prefKey}).")
                    return Result.success()
                }
                if (finalIntent.goal == GOAL_GREEK) {
                    Log.i("DelayedNagWorker", "Moussaka Exception: Reducing cooldown to 1.5h for Greek nag")
                }

                // --- Fire path: the only place expensive work is allowed ---
                val walkSummary = if (finalIntent.goal == GOAL_WALK) {
                    phases.add("health")
                    val healthManager = HealthConnectManager(applicationContext)
                    if (healthManager.hasForegroundPermissions()) healthManager.fetchRecentWalkData() else null
                } else null
                val hasPartialWalk = walkSummary != null &&
                    (walkSummary.walkingSessionsCount > 0 || walkSummary.totalDistanceMeters > 0.0) &&
                    walkSummary.totalSteps < 2000

                val llmMessage: String? = when (finalIntent.goal) {
                    GOAL_ARABIC -> {
                        phases.add("llm")
                        brain.generateNarrativeDirective(GOAL_ARABIC, isSensitive, null)
                    }
                    GOAL_WALK -> weather?.let {
                        phases.add("llm")
                        brain.generateNarrativeDirective(
                            if (hasPartialWalk) "MAJESTY CAKE" else GOAL_WALK,
                            isSensitive,
                            it.conditions,
                            it.is_dark
                        )
                    }
                    GOAL_GREEK -> {
                        phases.add("llm")
                        brain.generateNarrativeDirective(GOAL_GREEK, isSensitive, null)
                    }
                    else -> null
                }

                val payload = nagPayload(finalIntent, hasPartialWalk, isSensitive, hour)
                Log.i("DelayedNagWorker", "Firing Nag: ${payload.title} (LLM: ${llmMessage != null})")
                nagManager.showNag(payload.title, llmMessage ?: payload.message, payload.packageName, payload.nagType)
                phases.add("nag")

                val nowMs = Instant.now().toEpochMilli()
                prefs.edit()
                    .putLong(finalIntent.prefKey, nowMs)
                    .putLong(PREF_GLOBAL_LAST_NAG, nowMs)
                    .apply()
            } else {
                // 3. SOVEREIGN FALLBACK: Basic local walk check
                phases.add("fallback")
                val localHourFallback = java.time.LocalDateTime.now().hour
                val healthManager = HealthConnectManager(applicationContext)
                if (localHourFallback >= 8 && localHourFallback < 20 && healthManager.hasForegroundPermissions()) {
                    phases.add("health_fallback")
                    val summary = healthManager.fetchRecentWalkData()
                    if (summary.totalSteps < 2000) {
                        // CHECK COOLDOWN even for fallback nags
                        val nowMs = Instant.now().toEpochMilli()
                        val fourHoursAgoMs = nowMs - 14400000L
                        val lastGlobalNag = prefs.getLong(PREF_GLOBAL_LAST_NAG, 0L)

                        if (lastGlobalNag < fourHoursAgoMs) {
                            val hasPartialWalk = summary.walkingSessionsCount > 0 || summary.totalDistanceMeters > 0.0
                            val fallbackTitle = if (hasPartialWalk) "MAJESTY CAKE 🍰" else "BORIS & FIONA \uD83D\uDC15"
                            val fallbackMsg = if (hasPartialWalk) "You're on the path to the Majesty Cake! Keep the momentum going today. ✨" else "Time for a walk? Your steps are low today."

                            Log.i("DelayedNagWorker", "Firing Sovereign Fallback Nag: $fallbackTitle")
                            phases.add("nag")
                            nagManager.showNag(fallbackTitle, fallbackMsg, "com.google.android.apps.fitness", "walk_reminder")

                            prefs.edit()
                                .putLong(PREF_GLOBAL_LAST_NAG, nowMs)
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

    private data class NagPayload(val title: String, val message: String, val packageName: String?, val nagType: String)

    private fun nagPayload(intent: NagIntent, hasPartialWalk: Boolean, isSensitive: Boolean, hour: Int): NagPayload =
        when (intent.goal) {
            GOAL_ARABIC -> NagPayload(
                "ARABIC PRESSURE",
                "Your neural goal is in debt. Clear the cards. 📈",
                "com.clozemaster.v2",
                "arabic_pressure"
            )
            GOAL_WALK -> NagPayload(
                if (hasPartialWalk) "MAJESTY CAKE 🍰" else "PHYSICAL GOAL",
                if (hasPartialWalk) {
                    "You're on the path to the Majesty Cake! Keep the momentum going today. ✨"
                } else if (isSensitive) {
                    "Time for a walk? Your physical goal is waiting. 🚶"
                } else {
                    "Boris and Fiona are ready! 🐕 Time for a walk."
                },
                "com.google.android.apps.fitness",
                "walk_reminder"
            )
            GOAL_GREEK -> NagPayload(
                "GREEK ISLAND TIME 🏝️",
                greekNagMessage(arabicCleared = intent.arabicDone, isArabicHour = hour < 20),
                "com.clozemaster.v2",
                "greek_reminder"
            )
            else -> NagPayload("GOAL REMINDER", "Your goal is waiting. Time to make progress.", null, "unknown")
        }

    private fun isSensitiveMode(status: AggregateStatusResponseDto): Boolean {
        return status.vacation_mode_until?.let {
            try {
                val until = OffsetDateTime.parse(it).toInstant()
                Instant.now().isBefore(until)
            } catch (e: Exception) {
                false
            }
        } ?: false
    }

    private fun isCooldownCleared(prefKey: String, cooldownMs: Long): Boolean {
        val nowMs = Instant.now().toEpochMilli()
        val lastGoalNag = prefs.getLong(prefKey, 0L)
        val lastGlobalNag = prefs.getLong(PREF_GLOBAL_LAST_NAG, 0L)
        return lastGoalNag < (nowMs - cooldownMs) && lastGlobalNag < (nowMs - cooldownMs)
    }

    private suspend fun fetchWeatherOracle(): WeatherHeuristicResponseDto? {
        val lat = profileManager.getLatitude()?.toDoubleOrNull() ?: 40.7128
        val lon = profileManager.getLongitude()?.toDoubleOrNull() ?: -74.0060
        return try {
            val resp = syncApi.getWeatherHeuristic(lat, lon)
            if (resp.isSuccessful) resp.body() else null
        } catch (e: Exception) {
            null
        }
    }

    data class NagIntent(
        val goal: String,
        val prefKey: String,
        val cooldownMs: Long,
        val arabicDone: Boolean,
        val greekEligible: Boolean = false
    )

    companion object {
        const val GOAL_ARABIC = "ARABIC"
        const val GOAL_WALK = "WALK"
        const val GOAL_GREEK = "GREEK"

        /** Default per-goal + global cooldown (4 hours). */
        const val COOLDOWN_MS = 14_400_000L

        /** Moussaka Exception: tighter 1.5h window for Greek nags. */
        const val GREEK_COOLDOWN_MS = 5_400_000L

        const val PREF_GLOBAL_LAST_NAG = "global_last_nag_timestamp"

        fun greekNagMessage(arabicCleared: Boolean, isArabicHour: Boolean = true): String {
            return if (arabicCleared || !isArabicHour) {
                "The moussaka is waiting! Spend a moment in Mykonos. 🇬🇷"
            } else {
                "The moussaka is waiting, but the cards come first. Spend a moment in Mykonos. 🇬🇷"
            }
        }

        /**
         * Cheap nag-target selection: same hierarchy and hour gates as the old
         * evaluateNagHierarchy (Arabic > Walk > Greek), but with no network or
         * LLM work. Pure function; [minute] covers the Greek 22:30 cutoff.
         */
        fun evaluateNagIntent(
            arabicDone: Boolean,
            walkDone: Boolean,
            greekDone: Boolean,
            hour: Int,
            minute: Int
        ): NagIntent? {
            val isMoussakaHour = hour >= 17 && (hour < 22 || (hour == 22 && minute <= 30))
            val greekEligible = !greekDone && isMoussakaHour && (arabicDone || hour >= 20)

            // 1. ARABIC (Priority 1: High Pressure)
            if (!arabicDone && hour >= 8 && hour < 20) {
                return NagIntent(GOAL_ARABIC, "last_arabic_nag_timestamp", COOLDOWN_MS, arabicDone)
            }

            // 2. WALK / MAJESTY CAKE (Priority 2: Physical Wellbeing)
            if (!walkDone && hour >= 8 && hour < 20) {
                return NagIntent(GOAL_WALK, "last_walk_nag_timestamp", COOLDOWN_MS, arabicDone, greekEligible)
            }

            // 3. GREEK (Priority 3: Moussaka Final Boss)
            if (greekEligible) {
                return NagIntent(GOAL_GREEK, "last_greek_nag_timestamp", GREEK_COOLDOWN_MS, arabicDone)
            }

            return null
        }

        /**
         * Old-code semantics: a walk nag fires only when the weather oracle allows
         * (or is unavailable before 18:00, firing with a static message); darkness
         * or unsuitable weather falls through to the already-eligibility-checked
         * Greek fallback. Pure function.
         */
        fun resolveWalkIntent(intent: NagIntent, weather: WeatherHeuristicResponseDto?, hour: Int): NagIntent? = when {
            weather == null && hour < 18 -> intent
            weather == null -> intent.toGreekFallback()
            weather.is_dark -> intent.toGreekFallback()
            !weather.is_walk_appropriate -> intent.toGreekFallback()
            else -> intent
        }

        private fun NagIntent.toGreekFallback(): NagIntent? =
            if (greekEligible) copy(
                goal = GOAL_GREEK,
                prefKey = "last_greek_nag_timestamp",
                cooldownMs = GREEK_COOLDOWN_MS
            ) else null
    }
}
