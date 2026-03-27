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
}
