package com.mecris.go.sync

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.POST

interface SyncServiceApi {
    @POST("walks")
    suspend fun uploadWalk(
        @Header("Authorization") authHeader: String,
        @Body walkData: WalkDataSummaryDto
    ): SyncResponse

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
