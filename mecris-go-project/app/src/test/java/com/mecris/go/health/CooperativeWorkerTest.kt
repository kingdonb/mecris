package com.mecris.go.health

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.work.ListenableWorker
import androidx.work.OneTimeWorkRequest
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.mecris.go.auth.PocketIdAuthRepository
import com.mecris.go.sync.AggregateComponentsDto
import com.mecris.go.sync.AggregateStatusResponseDto
import com.mecris.go.sync.HeartbeatResponseDto
import com.mecris.go.sync.HelixBalanceRequestDto
import com.mecris.go.sync.SyncServiceApi
import com.google.gson.Gson
import io.mockk.*
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import java.io.File
import java.time.Instant

class CooperativeWorkerTest {
    private val context = mockk<Context>(relaxed = true)
    private val workerParams = mockk<WorkerParameters>(relaxed = true)
    private val syncApi = mockk<SyncServiceApi>()
    private val pocketIdAuth = mockk<PocketIdAuthRepository>()
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
        // Chain builder calls back onto the same editor mock so chained
        // putLong(...).apply() calls are recorded on prefsEditor
        every { prefsEditor.putLong(any(), any()) } returns prefsEditor
        every { prefsEditor.putString(any(), any()) } returns prefsEditor
        every { prefsEditor.clear() } returns prefsEditor
        every { sharedPrefs.getString("last_synced_day", "") } returns ""
        every { sharedPrefs.getLong("last_step_count", 0L) } returns 0L
        every { sharedPrefs.getLong("last_cloud_sync_trigger", 0L) } returns 0L
        // Battery diet (task 000622): helix doorbell throttle state
        every { sharedPrefs.getLong("last_helix_request", 0L) } returns 0L

        // Debt evaluation is aggregate-status-only now; default to all-clear so no
        // nag work is enqueued unless a test explicitly puts a goal in debt.
        coEvery { syncApi.getAggregateStatus(any()) } returns retrofit2.Response.success(
            aggregateStatus(arabic = true, walk = true, greek = true)
        )
        coEvery { syncApi.requestHelixBalanceSync(any()) } returns retrofit2.Response.success(
            HelixBalanceRequestDto(status = "ok", requested = true, last_balance = null, last_reading_ts = null)
        )

        coEvery { pocketIdAuth.getAccessTokenSuspend() } returns "fake_token"
    }

    @After
    fun tearDown() {
        unmockkAll()
    }

    private fun aggregateStatus(arabic: Boolean, walk: Boolean, greek: Boolean) =
        AggregateStatusResponseDto(
            score = if (arabic && walk && greek) "complete" else "partial",
            goals_met = listOf(arabic, walk, greek).count { it },
            total_goals = 3,
            all_clear = arabic && walk && greek,
            components = AggregateComponentsDto(walk = walk, arabic = arabic, greek = greek),
            vacation_mode_until = null
        )

    // --- #368: the cloud cron owns trigger-reminders and cloud-sync ---
    // Whatever the heartbeat says about the MCP server (dark, active, or the field
    // missing, which is what Spin actually sends), the phone never calls either.

    private fun heartbeatFromSpinContract(): HeartbeatResponseDto =
        Gson().fromJson(
            File("../../contracts/spin_heartbeat_response.json").readText(),
            HeartbeatResponseDto::class.java
        )

    // The trigger routes no longer exist on SyncServiceApi (SpinContractTest pins
    // that). At quiet hours the heartbeat must be the worker's only Spin call.
    private fun assertNoCloudWork() {
        coVerify(exactly = 1) { syncApi.sendHeartbeat(any(), any()) }
        confirmVerified(syncApi)
        verify(exactly = 0) { prefsEditor.putLong("last_cloud_sync_trigger", any()) }
    }

        @Test
        fun `worker never triggers cloud sync or reminders when MCP is dark`() = runBlocking {
        coEvery { syncApi.sendHeartbeat(any(), any()) } returns retrofit2.Response.success(
            HeartbeatResponseDto("ok", mcp_server_active = false)
        )

        WalkHeuristicsWorker(context, workerParams, pocketIdAuth, syncApi, etHourOverride = 3).doWork()

        assertNoCloudWork()
        }

        @Test
        fun `worker never triggers cloud sync or reminders when MCP is active`() = runBlocking {
        coEvery { syncApi.sendHeartbeat(any(), any()) } returns retrofit2.Response.success(
            HeartbeatResponseDto("ok", mcp_server_active = true)
        )

        WalkHeuristicsWorker(context, workerParams, pocketIdAuth, syncApi, etHourOverride = 3).doWork()

        assertNoCloudWork()
        }

        @Test
        fun `worker never triggers cloud sync or reminders when heartbeat omits mcp_server_active`() = runBlocking {
        // Spin's real /heartbeat body has no mcp_server_active field.
        coEvery { syncApi.sendHeartbeat(any(), any()) } returns retrofit2.Response.success(
            heartbeatFromSpinContract()
        )

        WalkHeuristicsWorker(context, workerParams, pocketIdAuth, syncApi, etHourOverride = 3).doWork()

        assertNoCloudWork()
        }

    // --- Battery diet (task 000622): helix doorbell throttle ---

        @Test
        fun `helix balance requested when interval elapsed during day`() = runBlocking {
        every { sharedPrefs.getLong("last_helix_request", 0L) } returns System.currentTimeMillis() - 2 * 60 * 60 * 1000L
        coEvery { syncApi.sendHeartbeat(any(), any()) } returns retrofit2.Response.success(
            HeartbeatResponseDto("ok", mcp_server_active = true)
        )

        val worker = WalkHeuristicsWorker(context, workerParams, pocketIdAuth, syncApi, etHourOverride = 12)

        worker.doWork()

        coVerify(exactly = 1) { syncApi.requestHelixBalanceSync(any()) }
        verify { prefsEditor.putLong("last_helix_request", any()) }
        }

        @Test
        fun `helix balance request throttled within the hour`() = runBlocking {
        every { sharedPrefs.getLong("last_helix_request", 0L) } returns System.currentTimeMillis() - 10 * 60 * 1000L
        coEvery { syncApi.sendHeartbeat(any(), any()) } returns retrofit2.Response.success(
            HeartbeatResponseDto("ok", mcp_server_active = true)
        )

        val worker = WalkHeuristicsWorker(context, workerParams, pocketIdAuth, syncApi, etHourOverride = 12)

        worker.doWork()

        coVerify(exactly = 0) { syncApi.requestHelixBalanceSync(any()) }
        }

    // --- Battery diet (task 000622): quiet hours gate ---

        @Test
        fun `nag phase and helix request skipped during quiet hours`() = runBlocking {
        coEvery { syncApi.sendHeartbeat(any(), any()) } returns retrofit2.Response.success(
            HeartbeatResponseDto("ok", mcp_server_active = true)
        )

        val worker = WalkHeuristicsWorker(context, workerParams, pocketIdAuth, syncApi, etHourOverride = 3)

        worker.doWork()

        coVerify(exactly = 0) { syncApi.getAggregateStatus(any()) }
        coVerify(exactly = 0) { syncApi.requestHelixBalanceSync(any()) }
        }

        @Test
        fun `nag phase checks aggregate during the day and no longer polls languages`() = runBlocking {
        coEvery { syncApi.sendHeartbeat(any(), any()) } returns retrofit2.Response.success(
            HeartbeatResponseDto("ok", mcp_server_active = true)
        )

        val worker = WalkHeuristicsWorker(context, workerParams, pocketIdAuth, syncApi, etHourOverride = 12)

        worker.doWork()

        coVerify(exactly = 1) { syncApi.getAggregateStatus(any()) }
        coVerify(exactly = 0) { syncApi.getLanguages(any()) }
        }

        @Test
        fun `goal debt detected from aggregate components enqueues nag work`() = runBlocking {
        mockkObject(WorkManager.Companion)
        val workManager = mockk<WorkManager>(relaxed = true)
        every { WorkManager.getInstance(any()) } returns workManager

        coEvery { syncApi.sendHeartbeat(any(), any()) } returns retrofit2.Response.success(
            HeartbeatResponseDto("ok", mcp_server_active = true)
        )
        coEvery { syncApi.getAggregateStatus(any()) } returns retrofit2.Response.success(
            aggregateStatus(arabic = false, walk = true, greek = true)
        )

        val worker = WalkHeuristicsWorker(context, workerParams, pocketIdAuth, syncApi, etHourOverride = 12)

        worker.doWork()

        verify(exactly = 1) {
            workManager.enqueueUniqueWork(eq("DelayedNagWork"), any(), any<OneTimeWorkRequest>())
        }
        }

}
