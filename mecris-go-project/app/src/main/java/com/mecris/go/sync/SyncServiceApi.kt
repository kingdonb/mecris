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

    @GET("budget")
    suspend fun getBudget(
        @Header("Authorization") authHeader: String
    ): retrofit2.Response<BudgetResponseDto>

    @GET("languages")
    suspend fun getLanguages(
        @Header("Authorization") authHeader: String
    ): retrofit2.Response<LanguagesResponseDto>

    @GET("health")
    suspend fun getHealth(
        @Header("Authorization") authHeader: String
    ): retrofit2.Response<HealthResponseDto>

    @POST("internal/cloud-sync")
    suspend fun triggerCloudSync(
        @Header("Authorization") authHeader: String
    ): retrofit2.Response<SyncResponse>

    @POST("internal/trigger-reminders")
    suspend fun triggerReminders(): retrofit2.Response<SyncResponse>

    @POST("heartbeat")
    suspend fun sendHeartbeat(
        @Header("Authorization") authHeader: String,
        @Body heartbeatData: HeartbeatRequestDto
    ): retrofit2.Response<HeartbeatResponseDto>

    @POST("languages/multiplier")
    suspend fun updateMultiplier(
        @Header("Authorization") authHeader: String,
        @Body request: MultiplierRequestDto
    ): retrofit2.Response<Unit>

    @GET("aggregate-status")
    suspend fun getAggregateStatus(
        @Header("Authorization") authHeader: String
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

data class BudgetResponseDto(
    val remaining_budget: Double
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
    val daily_completions: Int = 0
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
    val mcp_server_active: Boolean
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
    val phone_verified: Boolean = false
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

