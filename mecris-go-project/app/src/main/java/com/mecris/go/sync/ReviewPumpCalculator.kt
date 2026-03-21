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
            else -> "Custom"
        }
    }

    fun getClearanceDays(multiplier: Double): Int? {
        return when (multiplier.toInt()) {
            1 -> null
            2 -> 14
            3 -> 10
            4 -> 7
            5 -> 5
            6 -> 3
            7 -> 2
            else -> null
        }
    }

    fun calculateTargetFlowRate(multiplier: Double, currentDebt: Int, tomorrowLiability: Int): Int {
        val clearanceDays = getClearanceDays(multiplier)
        val backlogPortion = if (clearanceDays != null) currentDebt.toDouble() / clearanceDays else 0.0
        return (tomorrowLiability + backlogPortion).toInt()
    }
}
