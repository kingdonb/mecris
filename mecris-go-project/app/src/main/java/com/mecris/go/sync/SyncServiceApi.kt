package com.mecris.go.sync

import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Query
import java.util.concurrent.TimeUnit

interface SyncServiceApi {
    @POST("walks")
    suspend fun uploadWalk(
        @Header("Authorization") authHeader: String,
        @Body walkData: WalkDataSummaryDto
    ): retrofit2.Response<SyncResponse>

    @GET("languages")
    suspend fun getLanguages(
        @Header("Authorization") authHeader: String
    ): retrofit2.Response<LanguagesResponseDto>

    @GET("health")
    suspend fun getHealth(
        @Header("Authorization") authHeader: String
    ): retrofit2.Response<HealthResponseDto>

    // #368: no trigger-reminders or cloud-sync here. The cloud cron owns both;
    // SpinContractTest fails if either route comes back.

    @POST("heartbeat")
    suspend fun sendHeartbeat(
        @Header("Authorization") authHeader: String,
        @Body heartbeatData: HeartbeatRequestDto
    ): retrofit2.Response<HeartbeatResponseDto>

    // Task 588 Android hook: ask the backend for a Helix balance sync (leader runs the read+chart)
    @POST("helix-balance/request")
    suspend fun requestHelixBalanceSync(
        @Header("Authorization") authHeader: String
    ): retrofit2.Response<HelixBalanceRequestDto>

    @POST("languages/multiplier")
    suspend fun updateMultiplier(
        @Header("Authorization") authHeader: String,
        @Body request: MultiplierRequestDto
    ): retrofit2.Response<Unit>

    /**
     * [full] = true adds the pulse modalities and claude_plan (the dashboard only).
     * Workers leave it null, so Retrofit omits the query and their hourly calls stay light.
     */
    @GET("aggregate-status")
    suspend fun getAggregateStatus(
        @Header("Authorization") authHeader: String,
        @Query("full") full: Boolean? = null
    ): retrofit2.Response<AggregateStatusResponseDto>

    @GET("internal/weather-heuristic")
    suspend fun getWeatherHeuristic(
        @Query("lat") lat: Double,
        @Query("lon") lon: Double
    ): retrofit2.Response<WeatherHeuristicResponseDto>

    @POST("internal/request-phone-verification")
    suspend fun requestPhoneVerification(
        @Header("Authorization") authHeader: String,
        @Body request: PhoneVerificationRequestDto
    ): retrofit2.Response<SyncResponse>

    @POST("internal/confirm-phone-verification")
    suspend fun confirmPhoneVerification(
        @Header("Authorization") authHeader: String,
        @Body request: PhoneVerificationConfirmRequestDto
    ): retrofit2.Response<SyncResponse>

    /** #213: audit row for a shown local nag. Spin takes the user from the bearer. */
    @POST("internal/log-message")
    suspend fun logMessage(
        @Header("Authorization") authHeader: String,
        @Body request: LogMessageRequestDto
    ): retrofit2.Response<Unit>

    @GET("profile")
    suspend fun getProfile(
        @Header("Authorization") authHeader: String
    ): retrofit2.Response<ProfileResponseDto>

    @POST("profile")
    suspend fun updateProfile(
        @Header("Authorization") authHeader: String,
        @Body request: ProfileUpdateRequestDto
    ): retrofit2.Response<SyncResponse>

    companion object {
        fun create(baseUrl: String): SyncServiceApi {
            val client = OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(60, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .build()

            return Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(SyncServiceApi::class.java)
        }
    }
}

data class WalkDataSummaryDto(
    val start_time: String,
    val end_time: String,
    val step_count: Int,
    val distance_meters: Double,
    val distance_source: String,
    val confidence_score: Double,
    val gps_route_points: Int,
    val timezone: String
)

data class SyncResponse(
    val status: String,
    val message: String
)

data class LanguageStatDto(
    val name: String,
    val current: Int,
    val tomorrow: Int,
    val next_7_days: Int,
    val daily_rate: Double,
    val safebuf: Int,
    val derail_risk: String,
    val pump_multiplier: Double?,
    val has_goal: Boolean = true,
    val daily_completions: Int = 0,
    val target_flow_rate: Double? = null,
    val absolute_target: Int? = null,
    val goal_met: Boolean = false,
    val outstanding_debt: Int? = null
)

data class HealthResponseDto(
    val status: String,
    val home_server_active: Boolean,
    val leader_pid: String,
    val last_seen: String
)

data class LanguagesResponseDto(
    val languages: List<LanguageStatDto>
)

data class HeartbeatRequestDto(
    val role: String,
    val process_id: String
)

data class HeartbeatResponseDto(
    val status: String,
    // Spin's /heartbeat sends {status, message} only; null means "not reported",
    // never "MCP is dark" (Gson would otherwise default a missing Boolean to false).
    val mcp_server_active: Boolean? = null,
    val message: String? = null
)

// Task 588 Android hook: response to POST helix-balance/request
data class HelixBalanceRequestDto(
    val status: String,
    val requested: Boolean,
    val last_balance: String?,
    val last_reading_ts: String?
)

data class MultiplierRequestDto(
    val name: String,
    val multiplier: Double
)

data class AggregateComponentsDto(
    val walk: Boolean,
    val arabic: Boolean,
    val greek: Boolean
)

data class AggregateStatusResponseDto(
    val score: String,
    val goals_met: Int,
    val total_goals: Int,
    val all_clear: Boolean,
    val components: AggregateComponentsDto,
    val vacation_mode_until: String? = null,
    val phone_verified: Boolean = false,
    // v0.3.0 fields (contracts/spin_aggregate_status_full.json). All optional so the
    // app degrades gracefully against an older Spin: Gson leaves a missing field null.
    /** Only with ?full=true. */
    val modalities: List<ModalityDto>? = null,
    /** Only with ?full=true; null when no reading is recorded. */
    val claude_plan: ClaudePlanDto? = null,
    val pace: List<PaceDto>? = null
)

/** One system-pulse row; last_status is the cloud cron's latest outcome line. */
data class ModalityDto(
    val role: String? = null,
    val status: String? = null,
    val last_seen: String? = null,
    val minutes_since: Long? = null,
    val last_status: String? = null
)

/** Spin's derived Claude plan state (#344); the phone re-checks staleness against its clock. */
data class ClaudePlanDto(
    val state: String? = null,
    val reason: String? = null,
    val stale: Boolean? = null,
    val summary_line: String? = null,
    val plan: String? = null,
    val verified: Boolean? = null,
    val source: String? = null,
    val observed_at: String? = null,
    val age_minutes: Long? = null,
    val windows: List<ClaudePlanWindowDto>? = null
)

data class ClaudePlanWindowDto(
    val kind: String? = null,
    val pct_used: Double? = null,
    val resets_at: String? = null,
    val fresh: Boolean? = null
)

/** Reviews left today for a goal and the hourly pace to clear them by 22:00 New York (#349). */
data class PaceDto(
    val goal: String? = null,
    val remaining: Int? = null,
    val per_hour: Double? = null,
    val clear_by: String? = null,
    val due_today: Int? = null
)

data class WeatherHeuristicResponseDto(
    val is_walk_appropriate: Boolean,
    val conditions: String,
    val description: String,
    val temperature: Double,
    val sunrise: Long,
    val sunset: Long,
    val is_dark: Boolean,
    val now_epoch: Long,
    val data_ts: Long
)

data class PhoneVerificationRequestDto(
    val phone_number: String
)

data class PhoneVerificationConfirmRequestDto(
    val code: String
)

data class ProfileResponseDto(
    val phone_number: String?,
    val beeminder_user: String?,
    val latitude: Double?,
    val longitude: Double?,
    val vacation_mode_until: String?,
    val autonomous_sync_enabled: Boolean
)

data class ProfileUpdateRequestDto(
    val phone_number: String? = null,
    val beeminder_user: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val vacation_mode_until: String? = null,
    val autonomous_sync_enabled: Boolean? = null
)

data class LogMessageRequestDto(
    val type: String,
    val channel: String,
    val sent_at: String? = null
) {
    companion object {
        const val CHANNEL_ANDROID_NATIVE = "android_native"

        /** Spin's POST /internal/log-message type allowlist (#213). */
        val NAG_TYPES = setOf("walk_reminder", "arabic_pressure", "greek_reminder")

        /** The row for a nag the phone just showed. Never carries the message text. */
        fun shownNag(type: String, sentAt: java.time.Instant): LogMessageRequestDto =
            LogMessageRequestDto(type = type, channel = CHANNEL_ANDROID_NATIVE, sent_at = sentAt.toString())
    }
}

