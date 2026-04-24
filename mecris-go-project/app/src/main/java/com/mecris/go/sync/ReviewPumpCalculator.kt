package com.mecris.go.sync

object ReviewPumpCalculator {
    fun getLeverName(multiplier: Double): String {
        return when (multiplier.toInt()) {
            1 -> "Maintenance"
            2 -> "Steady"
            3 -> "Brisk"
            4 -> "Aggressive"
            5 -> "High Pressure"
            6 -> "Very High"
            7 -> "The Blitz"
            10 -> "System Overdrive"
            else -> "Custom"
        }
    }

    fun getClearanceDays(multiplier: Double): Double? {
        return when (multiplier.toInt()) {
            1 -> null
            2 -> 14.0
            3 -> 10.0
            4 -> 7.0
            5 -> 5.0
            6 -> 3.0
            7 -> 2.0
            10 -> 1.0
            else -> null
        }
    }

    fun calculateTargetFlowRate(multiplier: Double, currentDebt: Int, tomorrowLiability: Int): Int {
        val clearanceDays = getClearanceDays(multiplier)
        val backlogPortion = if (clearanceDays != null) currentDebt.toDouble() / clearanceDays else 0.0
        return (tomorrowLiability + backlogPortion).toInt()
    }

    /**
     * Returns the fraction of outstanding debt covered by today's completions.
     * 0.0 = no work done, 1.0+ = debt fully cleared.
     * Returns 0.0 if outstandingDebt is zero (nothing to cover).
     */
    fun calculateDebtCoverageRatio(completedToday: Int, outstandingDebt: Int): Float {
        if (outstandingDebt <= 0) return 0.0f
        return (completedToday.toFloat() / outstandingDebt.toFloat()).coerceAtLeast(0.0f)
    }

    /**
     * Returns the fraction of today's flow target covered by completions, capped at 1.0.
     * 0.0 = no work done, 1.0 = target met or exceeded.
     * Returns 0.0 if targetFlowRate is zero or negative.
     */
    fun calculateFlowFillRatio(completedToday: Int, targetFlowRate: Int): Float {
        if (targetFlowRate <= 0) return 0.0f
        return (completedToday.toFloat() / targetFlowRate.toFloat()).coerceIn(0.0f, 1.0f)
    }

    /**
     * Returns true when outstanding debt is large relative to the daily flow target,
     * signaling the user should "play" extra cards beyond the daily minimum.
     * Threshold: outstandingDebt > targetFlowRate * 7 (more than one week of daily work remaining).
     * Returns false if targetFlowRate is zero or negative.
     */
    fun calculateIsPlayMode(outstandingDebt: Int, targetFlowRate: Int): Boolean {
        if (targetFlowRate <= 0) return false
        return outstandingDebt > targetFlowRate * 7
    }

    /**
     * Returns true when outstanding debt is large enough to warrant creating a new
     * Beeminder reviewstack goal (≥ 300 cards outstanding).
     */
    fun calculateBeckonSignal(outstandingDebt: Int): Boolean {
        return outstandingDebt >= 300
    }
}
