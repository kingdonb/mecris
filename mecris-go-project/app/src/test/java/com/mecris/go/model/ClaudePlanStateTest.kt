package com.mecris.go.model

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.mecris.go.sync.AggregateStatusResponseDto
import com.mecris.go.sync.ClaudePlanDto
import com.mecris.go.sync.ClaudePlanWindowDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.time.Instant

/**
 * The phone re-derives the Claude plan state from cached Spin data against its own
 * clock, so a card cached yesterday turns 'unknown' instead of lying. The rules are
 * contracts/claude_plan_cases.json (read in place), the same table Python and Spin use.
 */
class ClaudePlanStateTest {
    private val gson = Gson()
    private val now = Instant.parse("2026-11-14T20:00:00Z")

    private fun contract(name: String) = File("../../contracts/$name").readText()

    private fun reading(observedAt: String, vararg windows: ClaudePlanWindowDto) = ClaudePlanDto(
        plan = "ultra", source = "manual", observed_at = observedAt, windows = windows.toList()
    )

    private fun weekly(pct: Double, resets: String = "2026-11-16T09:00:00Z") =
        ClaudePlanWindowDto(kind = "weekly_all", pct_used = pct, resets_at = resets)

    private fun session(pct: Double, resets: String = "2026-11-14T23:00:00Z") =
        ClaudePlanWindowDto(kind = "session", pct_used = pct, resets_at = resets)

    @Test
    fun `every contract case matches state, reason, stale, summary line and fresh windows`() {
        val cases = JsonParser.parseString(contract("claude_plan_cases.json")).asJsonObject.getAsJsonArray("cases")
        assertTrue(cases.size() >= 10)
        for (c in cases.map { it.asJsonObject }) {
            val name = c.get("name").asString
            val dto = gson.fromJson(c.get("reading"), ClaudePlanDto::class.java)
            val view = ClaudePlanState.derive(dto, Instant.parse(c.get("now").asString))
            val expect: JsonObject = c.getAsJsonObject("expect")
            assertEquals("$name state", expect.get("state").asString, view.state)
            assertEquals("$name reason", expect.get("reason").asString, view.reason)
            assertEquals("$name stale", expect.get("stale").asBoolean, view.stale)
            assertEquals("$name summary_line", expect.get("summary_line").asString, view.summaryLine)
            assertEquals(
                "$name fresh_window_kinds",
                expect.getAsJsonArray("fresh_window_kinds").map { it.asString },
                view.freshWindowKinds
            )
        }
    }

    @Test
    fun `available reading shows weekly percent, New York reset time and age`() {
        val view = ClaudePlanState.derive(reading("2026-11-14T19:00:00Z", weekly(62.4), session(20.0)), now)
        assertEquals("available", view.state)
        assertTrue(view.hasReading)
        assertEquals(62.4, view.weeklyPct!!, 0.001)
        assertEquals("Mon 4:00 AM", view.weeklyResetsLabel)
        assertEquals(60L, view.ageMinutes)
        assertEquals("ultra", view.plan)
    }

    @Test
    fun `over 80 percent is constrained`() {
        assertEquals("constrained", ClaudePlanState.derive(reading("2026-11-14T19:00:00Z", weekly(80.5)), now).state)
        assertEquals("available", ClaudePlanState.derive(reading("2026-11-14T19:00:00Z", weekly(80.0)), now).state)
    }

    @Test
    fun `100 percent is exhausted`() {
        assertEquals("exhausted", ClaudePlanState.derive(reading("2026-11-14T19:00:00Z", weekly(100.0)), now).state)
    }

    @Test
    fun `cached reading over 24 hours old turns unknown`() {
        val dto = reading("2026-11-13T19:59:00Z", weekly(40.0))
        assertEquals("available", ClaudePlanState.derive(dto, Instant.parse("2026-11-14T19:59:00Z")).state)
        val later = ClaudePlanState.derive(dto, now)
        assertEquals("unknown", later.state)
        assertTrue(later.stale)
        assertTrue(later.hasReading)
        assertNull(later.weeklyPct)
        assertEquals(1441L, later.ageMinutes)
    }

    @Test
    fun `cached reading whose weekly reset has passed turns unknown`() {
        val view = ClaudePlanState.derive(reading("2026-11-14T08:00:00Z", weekly(97.0, "2026-11-14T09:00:00Z")), now)
        assertEquals("unknown", view.state)
        assertEquals("weekly window has reset since the last reading", view.reason)
        assertNull(view.weeklyResetsLabel)
    }

    @Test
    fun `missing session window still renders`() {
        val view = ClaudePlanState.derive(reading("2026-11-14T19:00:00Z", weekly(40.0)), now)
        assertEquals("available", view.state)
        assertEquals(listOf("weekly_all"), view.freshWindowKinds)
        assertEquals("Claude: available (40% weekly, resets Mon 4:00 AM)", view.summaryLine)
    }

    @Test
    fun `null claude_plan renders no reading`() {
        val view = ClaudePlanState.derive(null, now)
        assertFalse(view.hasReading)
        assertEquals("unknown", view.state)
        assertEquals("no reading recorded", view.reason)
        assertNull(view.ageMinutes)
        assertNull(view.weeklyPct)
    }

    @Test
    fun `spin full aggregate claude_plan derives the same summary line`() {
        val agg = gson.fromJson(contract("spin_aggregate_status_full.json"), AggregateStatusResponseDto::class.java)
        val view = ClaudePlanState.derive(agg.claude_plan, now)
        assertEquals(agg.claude_plan!!.summary_line, view.summaryLine)
        assertEquals(agg.claude_plan!!.age_minutes, view.ageMinutes)
    }

    @Test
    fun `postgres style hour-only offsets still parse`() {
        val view = ClaudePlanState.derive(
            reading("2026-11-14 19:00:00+00", weekly(10.0, "2026-11-16 09:00:00+00")), now
        )
        assertEquals("available", view.state)
        assertEquals(60L, view.ageMinutes)
    }

    @Test
    fun `age labels`() {
        assertEquals("—", formatAge(null))
        assertEquals("just now", formatAge(0))
        assertEquals("42m ago", formatAge(42))
        assertEquals("1h ago", formatAge(60))
        assertEquals("23h ago", formatAge(1439))
        assertEquals("1d ago", formatAge(1440))
        assertEquals("15d ago", formatAge(22367))
        assertEquals("just now", formatAge(-3))
    }
}
