package com.mecris.go.model

import com.google.gson.Gson
import com.mecris.go.sync.AggregateComponentsDto
import com.mecris.go.sync.AggregateStatusResponseDto
import com.mecris.go.sync.ModalityDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class SystemPulseTest {
    private fun fromContract(): AggregateStatusResponseDto = Gson().fromJson(
        File("../../contracts/spin_aggregate_status_full.json").readText(),
        AggregateStatusResponseDto::class.java
    )

    private fun status(modalities: List<ModalityDto>?) = AggregateStatusResponseDto(
        score = "0/3", goals_met = 0, total_goals = 3, all_clear = false,
        components = AggregateComponentsDto(walk = false, arabic = false, greek = false),
        modalities = modalities
    )

    @Test
    fun `contract pulse lists each modality with status, age and the cron outcome`() {
        val rows = SystemPulse.rows(fromContract())
        assertEquals(listOf("ANDROID CLIENT", "AKAMAI FUNCTIONS", "MCP SERVER", "GHOST"), rows.map { it.role })
        assertEquals(PulseRow("AKAMAI FUNCTIONS", "healthy", "1h ago", "ok"), rows[1])
        assertEquals(PulseRow("ANDROID CLIENT", "healthy", "42m ago", null), rows[0])
        assertEquals(PulseRow("GHOST", "paused", "15d ago", null), rows[3])
    }

    @Test
    fun `no aggregate or no full=true modalities means no rows`() {
        assertTrue(SystemPulse.rows(null).isEmpty())
        assertTrue(SystemPulse.rows(status(null)).isEmpty())
    }

    @Test
    fun `today's live rows without last_status still render`() {
        val rows = SystemPulse.rows(status(listOf(ModalityDto(role = "AKAMAI", status = "healthy", minutes_since = 61))))
        assertEquals(listOf(PulseRow("AKAMAI", "healthy", "1h ago", null)), rows)
    }

    @Test
    fun `rows without a role are skipped, blanks tidy to defaults`() {
        val rows = SystemPulse.rows(status(listOf(
            ModalityDto(role = null, status = "healthy", minutes_since = 1),
            ModalityDto(role = "AKAMAI FUNCTIONS", status = null, minutes_since = null, last_status = "   ")
        )))
        assertEquals(1, rows.size)
        assertEquals("unknown", rows[0].status)
        assertEquals("—", rows[0].age)
        assertNull(rows[0].lastStatus)
    }
}
