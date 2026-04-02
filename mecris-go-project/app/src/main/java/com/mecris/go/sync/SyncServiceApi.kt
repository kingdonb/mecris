package com.mecris.go.sync

import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
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

    @POST("internal/failover-sync")
    suspend fun triggerFailoverSync(
        @Header("Authorization") authHeader: String
    ): retrofit2.Response<SyncResponse>

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
