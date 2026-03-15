package com.mecris.go.beeminder

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface BeeminderApi {
    @FormUrlEncoded
    @POST("api/v1/users/{user}/goals/{goal}/datapoints.json")
    suspend fun createDatapoint(
        @Path("user") user: String = "me",
        @Path("goal") goal: String,
        @Query("auth_token") authToken: String,
        @Field("value") value: Double,
        @Field("comment") comment: String,
        @Field("request_id") requestId: String // Idempotency key
    ): DatapointResponse

    companion object {
        fun create(): BeeminderApi {
            return Retrofit.Builder()
                .baseUrl("https://www.beeminder.com/")
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(BeeminderApi::class.java)
        }
    }
}

data class DatapointResponse(
    val id: String,
    val value: Double,
    val comment: String
)
