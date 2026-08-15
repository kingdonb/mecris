package com.mecris.go

import org.junit.Assert.assertEquals
import org.junit.Test

class MomentumVisualizerTest {

    @Test
    fun `all_clear takes priority over high momentum`() {
        assertEquals(MomentumOrbState.ALL_CLEAR, momentumOrbState(0.9f, isAllClear = true))
    }

    @Test
    fun `all_clear takes priority over low momentum`() {
        assertEquals(MomentumOrbState.ALL_CLEAR, momentumOrbState(0.1f, isAllClear = true))
    }

    @Test
    fun `all_clear takes priority over zero momentum`() {
        assertEquals(MomentumOrbState.ALL_CLEAR, momentumOrbState(0.0f, isAllClear = true))
    }

    @Test
    fun `stable state when momentum above 0_5 and not all_clear`() {
        assertEquals(MomentumOrbState.STABLE, momentumOrbState(0.6f, isAllClear = false))
    }

    @Test
    fun `stable state at maximum momentum`() {
        assertEquals(MomentumOrbState.STABLE, momentumOrbState(1.0f, isAllClear = false))
    }

    @Test
    fun `debt state at threshold boundary 0_5`() {
        assertEquals(MomentumOrbState.DEBT, momentumOrbState(0.5f, isAllClear = false))
    }

    @Test
    fun `debt state at zero momentum`() {
        assertEquals(MomentumOrbState.DEBT, momentumOrbState(0.0f, isAllClear = false))
    }

    @Test
    fun `debt state just below threshold`() {
        assertEquals(MomentumOrbState.DEBT, momentumOrbState(0.49f, isAllClear = false))
    }

    @Test
    fun `stable state just above threshold`() {
        assertEquals(MomentumOrbState.STABLE, momentumOrbState(0.51f, isAllClear = false))
    }

    @Test
    fun `calculateMomentum returns 0_6 (STABLE) when 2 of 3 goals are satisfied without walking`() {
        val aggregate = com.mecris.go.sync.AggregateStatusResponseDto(
            all_clear = false,
            score = "2/3",
            goals_met = 2,
            total_goals = 3,
            components = com.mecris.go.sync.AggregateComponentsDto(walk = false, arabic = true, greek = true)
        )
        // Even with zero steps and no walk inferred, 2/3 satisfied should yield 0.6f (STABLE / Green Orb)
        val momentum = calculateMomentum(isFetching = false, aggregateStatus = aggregate, walkData = null)
        assertEquals(0.6f, momentum, 0.001f)
        assertEquals(MomentumOrbState.STABLE, momentumOrbState(momentum, isAllClear = false))
    }

    @Test
    fun `calculateMomentum returns 1_0 (ALL_CLEAR) when all_clear is true`() {
        val aggregate = com.mecris.go.sync.AggregateStatusResponseDto(
            all_clear = true,
            score = "3/3",
            goals_met = 3,
            total_goals = 3,
            components = com.mecris.go.sync.AggregateComponentsDto(walk = true, arabic = true, greek = true)
        )
        val momentum = calculateMomentum(isFetching = false, aggregateStatus = aggregate, walkData = null)
        assertEquals(1.0f, momentum, 0.001f)
        assertEquals(MomentumOrbState.ALL_CLEAR, momentumOrbState(momentum, isAllClear = true))
    }

    @Test
    fun `calculateMomentum returns 0_3 (DEBT) when 0 of 3 goals are satisfied`() {
        val aggregate = com.mecris.go.sync.AggregateStatusResponseDto(
            all_clear = false,
            score = "0/3",
            goals_met = 0,
            total_goals = 3,
            components = com.mecris.go.sync.AggregateComponentsDto(walk = false, arabic = false, greek = false)
        )
        val momentum = calculateMomentum(isFetching = false, aggregateStatus = aggregate, walkData = null)
        assertEquals(0.3f, momentum, 0.001f)
        assertEquals(MomentumOrbState.DEBT, momentumOrbState(momentum, isAllClear = false))
    }
}
