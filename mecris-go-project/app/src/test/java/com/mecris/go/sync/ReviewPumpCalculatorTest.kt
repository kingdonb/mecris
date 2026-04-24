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

    @Test
    fun `debt coverage ratio is zero when no work done`() {
        val ratio = ReviewPumpCalculator.calculateDebtCoverageRatio(completedToday = 0, outstandingDebt = 500)
        assertEquals("No work done should be 0.0 coverage", 0.0f, ratio, 0.001f)
    }

    @Test
    fun `debt coverage ratio low progress typical session`() {
        // Arabic session: 50 cards completed, 2600 cards outstanding
        val ratio = ReviewPumpCalculator.calculateDebtCoverageRatio(completedToday = 50, outstandingDebt = 2600)
        assertEquals("50/2600 = ~0.019", 0.01923f, ratio, 0.001f)
    }

    @Test
    fun `debt coverage ratio debt cleared today`() {
        // Greek session: 80 cards completed, 80 outstanding
        val ratio = ReviewPumpCalculator.calculateDebtCoverageRatio(completedToday = 80, outstandingDebt = 80)
        assertEquals("Debt fully cleared should be 1.0", 1.0f, ratio, 0.001f)
    }

    @Test
    fun `debt coverage ratio exceeds one when over-cleared`() {
        val ratio = ReviewPumpCalculator.calculateDebtCoverageRatio(completedToday = 150, outstandingDebt = 80)
        assertEquals("Over-cleared ratio is 150/80 = 1.875", 1.875f, ratio, 0.001f)
    }

    @Test
    fun `debt coverage ratio is zero when outstanding debt is zero`() {
        val ratio = ReviewPumpCalculator.calculateDebtCoverageRatio(completedToday = 100, outstandingDebt = 0)
        assertEquals("Zero debt means 0.0 ratio (nothing to cover)", 0.0f, ratio, 0.001f)
    }

    @Test
    fun `flow fill ratio is zero when no work done`() {
        val ratio = ReviewPumpCalculator.calculateFlowFillRatio(completedToday = 0, targetFlowRate = 100)
        assertEquals("No work done should be 0.0 fill", 0.0f, ratio, 0.001f)
    }

    @Test
    fun `flow fill ratio is proportional when partially done`() {
        val ratio = ReviewPumpCalculator.calculateFlowFillRatio(completedToday = 50, targetFlowRate = 100)
        assertEquals("50/100 = 0.5 fill", 0.5f, ratio, 0.001f)
    }

    @Test
    fun `flow fill ratio is 1 when target exactly met`() {
        val ratio = ReviewPumpCalculator.calculateFlowFillRatio(completedToday = 150, targetFlowRate = 150)
        assertEquals("Target exactly met should be 1.0", 1.0f, ratio, 0.001f)
    }

    @Test
    fun `flow fill ratio caps at 1 when over-achieved`() {
        val ratio = ReviewPumpCalculator.calculateFlowFillRatio(completedToday = 200, targetFlowRate = 100)
        assertEquals("Over-achieved caps at 1.0 for UI bar", 1.0f, ratio, 0.001f)
    }

    @Test
    fun `flow fill ratio is zero when target is zero`() {
        val ratio = ReviewPumpCalculator.calculateFlowFillRatio(completedToday = 50, targetFlowRate = 0)
        assertEquals("Zero target means 0.0 ratio (nothing to fill)", 0.0f, ratio, 0.001f)
    }

    // --- calculateIsPlayMode ---

    @Test
    fun `play mode is false when debt is below threshold`() {
        // 100 cards debt, target 100/day -> 100 * 7 = 700; 100 < 700 -> not play mode
        val result = ReviewPumpCalculator.calculateIsPlayMode(outstandingDebt = 100, targetFlowRate = 100)
        assertEquals("Debt well below 7x target should not be play mode", false, result)
    }

    @Test
    fun `play mode is false when debt equals threshold exactly`() {
        // 700 debt, target 100/day -> 700 == 700; not strictly greater -> false
        val result = ReviewPumpCalculator.calculateIsPlayMode(outstandingDebt = 700, targetFlowRate = 100)
        assertEquals("Debt exactly at 7x threshold should not be play mode", false, result)
    }

    @Test
    fun `play mode is true when debt exceeds threshold`() {
        // Arabic: 2600 cards debt, target 100/day -> 2600 > 700 -> play mode
        val result = ReviewPumpCalculator.calculateIsPlayMode(outstandingDebt = 2600, targetFlowRate = 100)
        assertEquals("Large Arabic backlog should trigger play mode", true, result)
    }

    @Test
    fun `play mode is false when target flow rate is zero`() {
        val result = ReviewPumpCalculator.calculateIsPlayMode(outstandingDebt = 2600, targetFlowRate = 0)
        assertEquals("Zero target flow rate should not trigger play mode", false, result)
    }

    // --- calculateBeckonSignal ---

    @Test
    fun `beckon signal is false when debt is below threshold`() {
        val result = ReviewPumpCalculator.calculateBeckonSignal(outstandingDebt = 50)
        assertEquals("Small debt should not trigger beckon", false, result)
    }

    @Test
    fun `beckon signal is true when debt meets threshold exactly`() {
        val result = ReviewPumpCalculator.calculateBeckonSignal(outstandingDebt = 300)
        assertEquals("300 cards outstanding should trigger beckon at threshold", true, result)
    }

    @Test
    fun `beckon signal is true when debt exceeds threshold`() {
        val result = ReviewPumpCalculator.calculateBeckonSignal(outstandingDebt = 2600)
        assertEquals("2600 cards outstanding should strongly trigger beckon", true, result)
    }
}
