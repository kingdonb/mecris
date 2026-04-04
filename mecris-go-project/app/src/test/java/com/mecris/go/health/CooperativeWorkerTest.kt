package com.mecris.go.health

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.work.ListenableWorker
import androidx.work.WorkerParameters
import com.mecris.go.auth.PocketIdAuth
import com.mecris.go.sync.HeartbeatResponseDto
import com.mecris.go.sync.SyncResponse
import com.mecris.go.sync.SyncServiceApi
import io.mockk.*
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import java.time.Instant

class CooperativeWorkerTest {
    private val context = mockk<Context>(relaxed = true)
    private val workerParams = mockk<WorkerParameters>(relaxed = true)
    private val syncApi = mockk<SyncServiceApi>()
    private val pocketIdAuth = mockk<PocketIdAuth>()
    private val sharedPrefs = mockk<SharedPreferences>()
    private val prefsEditor = mockk<SharedPreferences.Editor>(relaxed = true)

    @Before
    fun setup() {
        mockkStatic(Log::class)
        every { Log.d(any(), any()) } returns 0
        every { Log.i(any(), any()) } returns 0
        every { Log.w(any(), any() as String) } returns 0
        every { Log.e(any(), any()) } returns 0

        every { context.getSharedPreferences("mecris_worker_state", Context.MODE_PRIVATE) } returns sharedPrefs
        every { sharedPrefs.edit() } returns prefsEditor
        every { sharedPrefs.getString("last_synced_day", "") } returns ""
        every { sharedPrefs.getLong("last_step_count", 0L) } returns 0L
        every { sharedPrefs.getLong("last_cloud_sync_trigger", 0L) } returns 0L
        
        coEvery { pocketIdAuth.getAccessTokenSuspend() } returns "fake_token"
    }

        @Test
        fun `worker triggers cloud sync when MCP is dark`() = runBlocking {
        // GIVEN: MCP is reported as NOT active
        coEvery { syncApi.sendHeartbeat(any(), any()) } returns retrofit2.Response.success(
            HeartbeatResponseDto("ok", mcp_server_active = false)
        )
        coEvery { syncApi.triggerCloudSync(any()) } returns retrofit2.Response.success(
            SyncResponse("ok", "cloud sync triggered")
        )
        coEvery { syncApi.getLanguages(any()) } returns retrofit2.Response.success(
            com.mecris.go.sync.LanguagesResponseDto(emptyList())
        )

        // GIVEN: We use the injected dependencies
        val worker = WalkHeuristicsWorker(context, workerParams, pocketIdAuth, syncApi)

        worker.doWork()

        // VERIFY: The cloud sync was triggered
        coVerify(exactly = 1) { syncApi.triggerCloudSync(any()) }
        }

        @Test
        fun `worker DOES NOT trigger cloud sync when MCP is active`() = runBlocking {
        // GIVEN: MCP is reported as active
        coEvery { syncApi.sendHeartbeat(any(), any()) } returns retrofit2.Response.success(
            HeartbeatResponseDto("ok", mcp_server_active = true)
        )
        coEvery { syncApi.getLanguages(any()) } returns retrofit2.Response.success(
            com.mecris.go.sync.LanguagesResponseDto(emptyList())
        )

        val worker = WalkHeuristicsWorker(context, workerParams, pocketIdAuth, syncApi)

        worker.doWork()

        // VERIFY: The cloud sync was NOT triggered
        coVerify(exactly = 0) { syncApi.triggerCloudSync(any()) }
        }

}
