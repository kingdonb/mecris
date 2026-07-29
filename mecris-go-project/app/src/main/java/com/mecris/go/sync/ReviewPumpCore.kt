package com.mecris.go.sync

/**
 * ReviewPumpCore — Pure Kotlin math for language review velocity calculations.
 *
 * Single source of truth for both Android UI and Python server (via review_pump_core.py).
 * No I/O, no config, no side effects — only pure functions and data classes.
 *
 * Keep in sync with services/review_pump_core.py — any formula change must be mirrored.
 */
data class PumpInput(
    val currentDebt: Int,           // Outstanding reviews (cards or points)
    val tomorrowLiability: Int,     // Reviews due tomorrow
    val dailyCompletions: Int,      // Cards/points completed today
    val multiplier: Double,         // Lever value (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 10.0)
    val minTarget: Int = 0          // Baseline floor (Greek=100, Arabic=0)
)

data class PumpOutput(
    val targetFlowRate: Int,                // Today's quota (tomorrow_liability + backlog portion)
    val targetFlowRateRemaining: Int,       // max(0, target - daily_completions)
    val currentFlowRate: Int,               // daily_completions (for backward compat)
    val goalMet: Boolean,
    val status: String,                     // "cavitation" | "laminar" | "turbulent"
    val debtCoverageRatio: Float,           // daily_completions / current_debt (0 if no debt, capped at 1.0)
    val flowFillRatio: Float,               // daily_completions / target_flow_rate (capped at 1.0)
    val isPlayMode: Boolean,                // debt > target * 7 (signal to play extra cards)
    val beckonSignal: Boolean,              // debt >= 300 (signal to create Beeminder goal)
    val leverName: String
)

object ReviewPumpCore {

    private val LEVER_CONFIG: Map<Int, Pair<String, Int?>> = mapOf(
        1 to "Maintenance" to null,
        2 to "Steady" to 14,
        3 to "Brisk" to 10,
        4 to "Aggressive" to 7,
        5 to "High Pressure" to 5,
        6 to "Very High" to 3,
        7 to "The Blitz" to 2,
        10 to "System Overdrive" to 1
    )

    fun clearanceDays(multiplier: Double): Int? {
        return LEVER_CONFIG[multiplier.toInt()]?.second
    }

    fun leverName(multiplier: Double): String {
        return LEVER_CONFIG[multiplier.toInt()]?.first ?: "Custom"
    }

    fun calculateTargetFlowRate(input: PumpInput): Int {
        val days = clearanceDays(input.multiplier)
        val backlog = if (days != null) input.currentDebt / days else 0
        val target = input.tomorrowLiability + backlog
        return max(target, input.minTarget)
    }

    fun calculateGoalMet(input: PumpInput, targetFlowRate: Int): Boolean {
        // Vacuous success: no debt, no liability
        if (input.currentDebt == 0 && input.tomorrowLiability == 0) return true
        // Normal: target > 0 OR (debt > 0 AND multiplier > 1.0) -> compare completions
        if (targetFlowRate > 0 || (input.currentDebt > 0 && input.multiplier > 1.0)) {
            return input.dailyCompletions >= targetFlowRate
        }
        // Maintenance (1.0) with zero target: goal met only if no debt
        return input.currentDebt == 0
    }

    fun calculateDebtCoverageRatio(input: PumpInput): Float {
        if (input.currentDebt <= 0) return 0.0f
        return (input.dailyCompletions.toFloat() / input.currentDebt.toFloat()).coerceAtLeast(0.0f).coerceAtMost(1.0f)
    }

    fun calculateFlowFillRatio(input: PumpInput, targetFlowRate: Int): Float {
        if (targetFlowRate <= 0) return 0.0f
        return (input.dailyCompletions.toFloat() / targetFlowRate.toFloat()).coerceIn(0.0f, 1.0f)
    }

    fun calculateIsPlayMode(input: PumpInput, targetFlowRate: Int): Boolean {
        if (targetFlowRate <= 0) return false
        return input.currentDebt > targetFlowRate * 7
    }

    fun calculateBeckonSignal(input: PumpInput): Boolean {
        return input.currentDebt >= 300
    }

    fun calculateStatus(input: PumpInput, targetFlowRate: Int): String {
        // Vacuous laminar
        if (input.currentDebt == 0 && input.tomorrowLiability == 0) return "laminar"
        // Cavitation: below tomorrow's liability
        if (input.dailyCompletions < input.tomorrowLiability) return "cavitation"
        // Turbulent: at or above target
        if (targetFlowRate > 0 && input.dailyCompletions >= targetFlowRate) return "turbulent"
        // Laminar: between liability and target
        return "laminar"
    }

    fun runPump(input: PumpInput): PumpOutput {
        val target = calculateTargetFlowRate(input)
        return PumpOutput(
            targetFlowRate = target,
            targetFlowRateRemaining = max(0, target - input.dailyCompletions),
            currentFlowRate = input.dailyCompletions,
            goalMet = calculateGoalMet(input, target),
            status = calculateStatus(input, target),
            debtCoverageRatio = calculateDebtCoverageRatio(input),
            flowFillRatio = calculateFlowFillRatio(input, target),
            isPlayMode = calculateIsPlayMode(input, target),
            beckonSignal = calculateBeckonSignal(input),
            leverName = leverName(input.multiplier)
        )
    }
}