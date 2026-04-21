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
}
