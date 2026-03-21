package com.mecris.go.sync

import org.junit.Assert.assertEquals
import org.junit.Test

class ReviewPumpCalculatorTest {

    @Test
    fun `maintenance lever only clears tomorrow liabilities`() {
        // 1x -> Maintenance (only clear tomorrow liability)
        val target = ReviewPumpCalculator.calculateTargetFlowRate(
            multiplier = 1.0,
            currentDebt = 2608,
            tomorrowLiability = 100
        )
        assertEquals("Target should match tomorrow liability", 100, target)
        assertEquals("Maintenance", ReviewPumpCalculator.getLeverName(1.0))
    }

    @Test
    fun `steady lever clears debt over 14 days`() {
        // 2x -> Steady (14 days)
        val target = ReviewPumpCalculator.calculateTargetFlowRate(
            multiplier = 2.0,
            currentDebt = 1400,
            tomorrowLiability = 0
        )
        assertEquals("Target should be 1/14th of 1400", 100, target)
        assertEquals("Steady", ReviewPumpCalculator.getLeverName(2.0))
    }

    @Test
    fun `aggressive lever targets akrasia horizon`() {
        // 4x -> Aggressive (7 days / Akrasia Horizon)
        val target = ReviewPumpCalculator.calculateTargetFlowRate(
            multiplier = 4.0,
            currentDebt = 700,
            tomorrowLiability = 50
        )
        // 700 / 7 = 100 + 50 = 150
        assertEquals("Target should be 1/7th of 700 plus liability", 150, target)
        assertEquals("Aggressive", ReviewPumpCalculator.getLeverName(4.0))
    }

    @Test
    fun `blitz lever targets 2 days`() {
        // 7x -> The Blitz (2 days)
        val target = ReviewPumpCalculator.calculateTargetFlowRate(
            multiplier = 7.0,
            currentDebt = 1000,
            tomorrowLiability = 20
        )
        // 1000 / 2 = 500 + 20 = 520
        assertEquals("Target should be half of 1000 plus liability", 520, target)
        assertEquals("The Blitz", ReviewPumpCalculator.getLeverName(7.0))
    }
}
