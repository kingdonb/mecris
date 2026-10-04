package com.mecris.go.health

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.work.WorkerParameters
import com.mecris.go.ai.SovereignBrain
import com.mecris.go.auth.PocketIdAuthRepository
import com.mecris.go.sync.AggregateComponentsDto
import com.mecris.go.sync.AggregateStatusResponseDto
import com.mecris.go.sync.NagNotificationManager
import com.mecris.go.sync.SyncServiceApi
import com.mecris.go.sync.WeatherHeuristicResponseDto
import io.mockk.*
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

/**
 * Battery-diet regression tests (task 000622): the nag worker must spend
 * weather fetches, Health Connect reads, and on-device LLM inference only
 * when a nag will actually fire.
 */
class DelayedNagWorkerGateTest {
    private val context = mockk<Context>(relaxed = true)
    private val workerParams = mockk<WorkerParameters>(relaxed = true)
    private val syncApi = mockk<SyncServiceApi>()
    private val pocketIdAuth = mockk<PocketIdAuthRepository>()
    private val brain = mockk<SovereignBrain>()
    private val nagManager = mockk<NagNotificationManager>(relaxed = true)
    private val sharedPrefs = mockk<SharedPreferences>()
    private val prefsEditor = mockk<SharedPreferences.Editor>(relaxed = true)
    private val healthManager = mockk<HealthConnectManager>(relaxed = true)

    @Before
    fun setup() {
        mockkStatic(Log::class)
        every { Log.d(any(), any()) } returns 0
        every { Log.i(any(), any()) } returns 0
        every { Log.w(any(), any() as String) } returns 0
        every { Log.e(any(), any()) } returns 0

        every { context.getSharedPreferences("mecris_worker_state", Context.MODE_PRIVATE) } returns sharedPrefs
        every { context.getSharedPreferences("mecris_app_prefs", Context.MODE_PRIVATE) } returns mockk(relaxed = true)
        every { sharedPrefs.edit() } returns prefsEditor
        // Chain builder calls back onto the same editor mock so chained
        // putLong(...).putLong(...).apply() calls are all recorded on prefsEditor
        every { prefsEditor.putLong(any(), any()) } returns prefsEditor
        every { prefsEditor.putString(any(), any()) } returns prefsEditor
        every { prefsEditor.clear() } returns prefsEditor
        every { sharedPrefs.getLong(any(), any()) } returns 0L
        every { sharedPrefs.getString(any(), any()) } returns null

        coEvery { pocketIdAuth.getAccessTokenSuspend() } returns "fake_token"
        coEvery { brain.generateNarrativeDirective(any(), any(), any(), any()) } returns "LLM nag"
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

    private fun worker(hour: Int) = DelayedNagWorker(
        context, workerParams, pocketIdAuth, syncApi, brain, nagManager,
        injectedHealthManager = healthManager, injectedHour = hour
    )

    private fun stubAggregate(arabic: Boolean, walk: Boolean, greek: Boolean) {
        coEvery { syncApi.getAggregateStatus(any()) } returns retrofit2.Response.success(
            aggregateStatus(arabic, walk, greek)
        )
    }

    // --- Cooldown gates before expensive work ---

        @Test
        fun `nag suppressed by cooldown does not spend weather or LLM`() = runBlocking {
        stubAggregate(arabic = false, walk = true, greek = true)
        val nowMs = System.currentTimeMillis()
        every { sharedPrefs.getLong("last_arabic_nag_timestamp", 0L) } returns nowMs
        every { sharedPrefs.getLong("global_last_nag_timestamp", 0L) } returns nowMs

        worker(hour = 10).doWork()

        coVerify(exactly = 0) { brain.generateNarrativeDirective(any(), any(), any(), any()) }
        coVerify(exactly = 0) { syncApi.getWeatherHeuristic(any(), any()) }
        verify(exactly = 0) { nagManager.showNag(any(), any(), any(), any()) }
        verify(exactly = 0) { prefsEditor.putLong(any(), any()) }
        }

        @Test
        fun `arabic nag fires when cooldown cleared and only then calls LLM`() = runBlocking {
        stubAggregate(arabic = false, walk = true, greek = true)

        worker(hour = 10).doWork()

        coVerify(exactly = 1) { brain.generateNarrativeDirective("ARABIC", false, null, false) }
        verify(exactly = 1) { nagManager.showNag("ARABIC PRESSURE", "LLM nag", "com.clozemaster.v2", "arabic_pressure") }
        verify { prefsEditor.putLong("last_arabic_nag_timestamp", any()) }
        verify { prefsEditor.putLong("global_last_nag_timestamp", any()) }
        }

        @Test
        fun `walk suppressed without greek fallback skips weather`() = runBlocking {
        stubAggregate(arabic = true, walk = false, greek = true)
        val nowMs = System.currentTimeMillis()
        every { sharedPrefs.getLong("last_walk_nag_timestamp", 0L) } returns nowMs
        every { sharedPrefs.getLong("global_last_nag_timestamp", 0L) } returns nowMs

        worker(hour = 10).doWork()

        coVerify(exactly = 0) { syncApi.getWeatherHeuristic(any(), any()) }
        coVerify(exactly = 0) { brain.generateNarrativeDirective(any(), any(), any(), any()) }
        verify(exactly = 0) { nagManager.showNag(any(), any(), any(), any()) }
        }

        @Test
        fun `all clear means no nag and no llm`() = runBlocking {
        stubAggregate(arabic = true, walk = true, greek = true)

        worker(hour = 10).doWork()

        coVerify(exactly = 0) { brain.generateNarrativeDirective(any(), any(), any(), any()) }
        verify(exactly = 0) { nagManager.showNag(any(), any(), any(), any()) }
        }

        @Test
        fun `outside nag windows means no nag`() = runBlocking {
        stubAggregate(arabic = false, walk = false, greek = false)

        worker(hour = 3).doWork()

        coVerify(exactly = 0) { brain.generateNarrativeDirective(any(), any(), any(), any()) }
        verify(exactly = 0) { nagManager.showNag(any(), any(), any(), any()) }
        }

    // --- Walk weather resolution (old evaluateNagHierarchy semantics) ---

        @Test
        fun `dark weather falls through to greek when greek eligible`() = runBlocking {
        stubAggregate(arabic = true, walk = false, greek = false)
        coEvery { brain.generateNarrativeDirective("GREEK", any(), any(), any()) } returns null
        coEvery { syncApi.getWeatherHeuristic(any(), any()) } returns retrofit2.Response.success(
            WeatherHeuristicResponseDto(
                is_walk_appropriate = false,
                conditions = "clear",
                description = "Clear",
                temperature = 15.0,
                sunrise = 0L,
                sunset = 0L,
                is_dark = true,
                now_epoch = 0L,
                data_ts = 0L
            )
        )

        worker(hour = 18).doWork()

        // Greek fallback fires; the LLM stub returns null for GREEK so the static
        // moussaka message is used
        verify(exactly = 1) { nagManager.showNag(eq("GREEK ISLAND TIME 🏝️"), match { it.contains("moussaka", ignoreCase = true) }, "com.clozemaster.v2", "greek_reminder") }
        verify { prefsEditor.putLong("last_greek_nag_timestamp", any()) }
        verify { prefsEditor.putLong("global_last_nag_timestamp", any()) }
        }

        @Test
        fun `suitable weather fires walk nag with llm`() = runBlocking {
        stubAggregate(arabic = true, walk = false, greek = true)
        coEvery { syncApi.getWeatherHeuristic(any(), any()) } returns retrofit2.Response.success(
            WeatherHeuristicResponseDto(
                is_walk_appropriate = true,
                conditions = "sunny",
                description = "Sunny",
                temperature = 20.0,
                sunrise = 0L,
                sunset = 0L,
                is_dark = false,
                now_epoch = 0L,
                data_ts = 0L
            )
        )

        worker(hour = 12).doWork()

        coVerify(exactly = 1) { brain.generateNarrativeDirective("WALK", false, "sunny", false) }
        verify(exactly = 1) { nagManager.showNag(eq("PHYSICAL GOAL"), any(), "com.google.android.apps.fitness", "walk_reminder") }
        verify { prefsEditor.putLong("last_walk_nag_timestamp", any()) }
        }

    // --- Pure intent selection (evaluateNagIntent) ---

    @Test
    fun `intent picks arabic first then walk then greek`() {
        // All in debt at 10:00 → arabic wins
        val first = DelayedNagWorker.evaluateNagIntent(arabicDone = false, walkDone = false, greekDone = false, hour = 10, minute = 0)
        assertEquals(DelayedNagWorker.GOAL_ARABIC, first?.goal)

        // Arabic done, walk in debt at 10:00 → walk
        val second = DelayedNagWorker.evaluateNagIntent(arabicDone = true, walkDone = false, greekDone = false, hour = 10, minute = 0)
        assertEquals(DelayedNagWorker.GOAL_WALK, second?.goal)
        // Greek not eligible at 10:00 (outside moussaka hour)
        assertEquals(false, second?.greekEligible)

        // Arabic + walk done, greek in debt at 18:00 (moussaka, arabic cleared) → greek
        val third = DelayedNagWorker.evaluateNagIntent(arabicDone = true, walkDone = true, greekDone = false, hour = 18, minute = 0)
        assertEquals(DelayedNagWorker.GOAL_GREEK, third?.goal)
        assertEquals(DelayedNagWorker.GREEK_COOLDOWN_MS, third?.cooldownMs)
    }

    @Test
    fun `greek eligible only during moussaka hour with arabic cleared or late hour`() {
        // 16:59 → not moussaka hour
        assertNull(DelayedNagWorker.evaluateNagIntent(true, true, false, 16, 59))
        // 22:00 with minute 30 → still eligible
        assertNotNull(DelayedNagWorker.evaluateNagIntent(true, true, false, 22, 30))
        // 22:00 with minute 31 → closed
        assertNull(DelayedNagWorker.evaluateNagIntent(true, true, false, 22, 31))
        // 18:00, arabic NOT done → arabic still in its window, so arabic wins
        // (greek would also be blocked: arabic not cleared and hour < 20)
        assertEquals(DelayedNagWorker.GOAL_ARABIC, DelayedNagWorker.evaluateNagIntent(false, true, false, 18, 0)?.goal)
        // 21:00, arabic NOT done → arabic window closed → greek allowed
        assertEquals(DelayedNagWorker.GOAL_GREEK, DelayedNagWorker.evaluateNagIntent(false, true, false, 21, 0)?.goal)
        // 19:00 → outside arabic window? no: 19 < 20 → arabic still in window
        assertEquals(DelayedNagWorker.GOAL_ARABIC, DelayedNagWorker.evaluateNagIntent(false, true, false, 19, 0)?.goal)
    }

    @Test
    fun `walk intent carries greek eligibility for weather fallback`() {
        // 18:00, greek in debt, arabic cleared → walk intent can fall through
        val intent = DelayedNagWorker.evaluateNagIntent(true, false, false, 18, 0)
        assertEquals(DelayedNagWorker.GOAL_WALK, intent?.goal)
        assertEquals(true, intent?.greekEligible)

        // 12:00, greek not in moussaka hour → no fallback
        val noon = DelayedNagWorker.evaluateNagIntent(true, false, false, 12, 0)
        assertEquals(false, noon?.greekEligible)
    }

    @Test
    fun `resolveWalkIntent old semantics`() {
        val intent = DelayedNagWorker.evaluateNagIntent(true, false, false, 18, 0)!!
        val greekFallback = intent.copy(
            goal = DelayedNagWorker.GOAL_GREEK,
            prefKey = "last_greek_nag_timestamp",
            cooldownMs = DelayedNagWorker.GREEK_COOLDOWN_MS
        )

        // Suitable weather → walk stays
        assertEquals(intent, DelayedNagWorker.resolveWalkIntent(intent, weather(isDark = false, appropriate = true), 18))
        // Dark → greek fallback (eligible)
        assertEquals(greekFallback, DelayedNagWorker.resolveWalkIntent(intent, weather(isDark = true, appropriate = true), 18))
        // Unsuitable (not dark) → greek fallback (old code fell past both weather ifs)
        assertEquals(greekFallback, DelayedNagWorker.resolveWalkIntent(intent, weather(isDark = false, appropriate = false), 18))
        // No weather before 18:00 → walk with static message
        assertEquals(intent, DelayedNagWorker.resolveWalkIntent(intent, null, 17))
        // No weather at/after 18:00 → greek fallback
        assertEquals(greekFallback, DelayedNagWorker.resolveWalkIntent(intent, null, 18))
        // Dark but greek NOT eligible → nothing
        val noon = DelayedNagWorker.evaluateNagIntent(true, false, false, 12, 0)!!
        assertNull(DelayedNagWorker.resolveWalkIntent(noon, weather(isDark = true, appropriate = true), 12))
    }

    private fun weather(isDark: Boolean, appropriate: Boolean) = WeatherHeuristicResponseDto(
        is_walk_appropriate = appropriate,
        conditions = "test",
        description = "Test",
        temperature = 15.0,
        sunrise = 0L,
        sunset = 0L,
        is_dark = isDark,
        now_epoch = 0L,
        data_ts = 0L
    )
}
