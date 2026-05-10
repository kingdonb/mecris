package com.useless.moonphase

import org.junit.Assert.assertTrue
import org.junit.Test

class WasmEngineTest {

    @Test
    fun `test wasm engine loads and calculates full moon`() {
        // We simulate passing a known Full Moon timestamp to the engine.
        // Full Moon example: ~2025-01-13 22:27:00 UTC (1736807220.0)
        
        val wasmStream = this::class.java.classLoader?.getResourceAsStream("moon-phase.wasm")
            ?: throw IllegalStateException("Could not find moon-phase.wasm in test resources")
            
        val engine = WasmEngine(wasmStream)
        val resultJson = engine.calculatePhase(1736807220.0)
        
        println("WASM Result: $resultJson")
        
        // Assert the Torment Multiplier is Maxed out and it identified the Full Moon
        assertTrue("Expected Full Moon in JSON", resultJson.contains("\"phase_name\": \"Full Moon\""))
        assertTrue("Expected Torment Multiplier 3.0", resultJson.contains("\"torment_multiplier\": 3.0"))
    }
}
