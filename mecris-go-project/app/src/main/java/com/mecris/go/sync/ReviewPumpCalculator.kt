package com.mecris.go.sync

/**
 * ReviewPumpCalculator — Thin wrapper around ReviewPumpCore for Android UI.
 *
 * All math now lives in ReviewPumpCore (synced with Python review_pump_core.py).
 * This object only provides convenience methods matching the old API surface.
 */
object ReviewPumpCalculator {

    fun getLeverName(multiplier: Double): String {
        return ReviewPumpCore.leverName(multiplier)
    }

    fun getClearanceDays(multiplier: Double): Double? {
        return ReviewPumpCore.clearanceDays(multiplier)?.toDouble()
    }

    fun calculateTargetFlowRate(multiplier: Double, currentDebt: Int, tomorrowLiability: Int): Int {
        val input = PumpInput(
            currentDebt = currentDebt,
            tomorrowLiability = tomorrowLiability,
            dailyCompletions = 0,
            multiplier = multiplier,
            minTarget = 0
        )
        return ReviewPumpCore.calculateTargetFlowRate(input)
    }

    fun calculateTargetFlowRateWithMinTarget(
        multiplier: Double,
        currentDebt: Int,
        tomorrowLiability: Int,
        minTarget: Int
    ): Int {
        val input = PumpInput(
            currentDebt = currentDebt,
            tomorrowLiability = tomorrowLiability,
            dailyCompletions = 0,
            multiplier = multiplier,
            minTarget = minTarget
        )
        return ReviewPumpCore.calculateTargetFlowRate(input)
    }

    fun calculateDebtCoverageRatio(completedToday: Int, outstandingDebt: Int): Float {
        val input = PumpInput(
            currentDebt = outstandingDebt,
            tomorrowLiability = 0,
            dailyCompletions = completedToday,
            multiplier = 1.0,
            minTarget = 0
        )
        return ReviewPumpCore.calculateDebtCoverageRatio(input)
    }

    fun calculateFlowFillRatio(completedToday: Int, targetFlowRate: Int): Float {
        val input = PumpInput(
            currentDebt = 0,
            tomorrowLiability = 0,
            dailyCompletions = completedToday,
            multiplier = 1.0,
            minTarget = 0
        )
        return ReviewPumpCore.calculateFlowFillRatio(input, targetFlowRate)
    }

    fun calculateIsPlayMode(outstandingDebt: Int, targetFlowRate: Int): Boolean {
        val input = PumpInput(
            currentDebt = outstandingDebt,
            tomorrowLiability = 0,
            dailyCompletions = 0,
            multiplier = 1.0,
            minTarget = 0
        )
        return ReviewPumpCore.calculateIsPlayMode(input, targetFlowRate)
    }

    fun calculateBeckonSignal(outstandingDebt: Int): Boolean {
        val input = PumpInput(
            currentDebt = outstandingDebt,
            tomorrowLiability = 0,
            dailyCompletions = 0,
            multiplier = 1.0,
            minTarget = 0
        )
        return ReviewPumpCore.calculateBeckonSignal(input)
    }

    fun calculateGoalMet(goalMetFromServer: Boolean, targetFlowRate: Double?): Boolean {
        // This uses server-provided flag as primary, with fallback
        return goalMetFromServer || (targetFlowRate != null && targetFlowRate <= 0.0)
    }

    /**
     * Full pump calculation returning all fields for UI rendering.
     * Mirrors ReviewPumpCore.runPump but with Android-friendly naming.
     */
    fun runPump(
        currentDebt: Int,
        tomorrowLiability: Int,
        dailyCompletions: Int,
        multiplier: Double,
        minTarget: Int = 0
    ): PumpOutput {
        val input = PumpInput(
            currentDebt = currentDebt,
            tomorrowLiability = tomorrowLiability,
            dailyCompletions = dailyCompletions,
            multiplier = multiplier,
            minTarget = minTarget
        )
        return ReviewPumpCore.runPump(input)
    }
}