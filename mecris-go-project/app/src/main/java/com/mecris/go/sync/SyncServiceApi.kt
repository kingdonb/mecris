package com.mecris.go.sync

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

interface SyncServiceApi {
    @POST("walks")
    suspend fun uploadWalk(
        @Header("Authorization") authHeader: String,
        @Body walkData: WalkDataSummaryDto
    ): SyncResponse

    @GET("budget")
    suspend fun getBudget(
        @Header("Authorization") authHeader: String
    ): BudgetResponseDto

    @GET("languages")
    suspend fun getLanguages(
        @Header("Authorization") authHeader: String
    ): LanguagesResponseDto

    @GET("health")
    suspend fun getHealth(
        @Header("Authorization") authHeader: String
    ): HealthResponseDto

    @GET("internal/failover-sync")
    suspend fun triggerFailoverSync(
        @Header("Authorization") authHeader: String
    ): SyncResponse

    @POST("heartbeat")
    suspend fun sendHeartbeat(
        @Header("Authorization") authHeader: String,
        @Body heartbeatData: HeartbeatRequestDto
    ): HeartbeatResponseDto

    @POST("languages/multiplier")
    suspend fun updateMultiplier(
        @Header("Authorization") authHeader: String,
        @Body request: MultiplierRequestDto
    ): retrofit2.Response<Unit>

    companion object {
        fun create(baseUrl: String): SyncServiceApi {
            return Retrofit.Builder()
                .baseUrl(baseUrl)
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
    val pump_multiplier: Double? = 1.0,
    val has_goal: Boolean = true
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
