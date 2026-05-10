package com.useless.moonphase

import com.dylibso.chicory.runtime.Instance
import com.dylibso.chicory.wasm.Parser
import java.io.InputStream

/**
 * The Zero-Split-Brain Wasm Engine for Android.
 * 
 * This class loads the 'moon-phase.wasm' file using the Chicory pure-Java
 * interpreter. It executes the math locally without needing the cloud API.
 */
class WasmEngine(wasmInputStream: InputStream) {

    private val module = Parser.parse(wasmInputStream)
    private val instance = Instance.builder(module).build()

    fun calculatePhase(timestamp: Double): String {
        val func = instance.export("calculate_moon_phase")

        // Execute the math using the raw long API for Chicory 1.0.0-M2.
        // For f64, we must pass the raw bits as a long.
        val timestampBits = java.lang.Double.doubleToRawLongBits(timestamp)
        val results = func.apply(timestampBits)

        // The return value is the pointer to the RESULT_BUFFER (i32)
        val ptr = results[0].toInt()

        // Read the null-terminated string from Wasm memory
        val memory = instance.memory()
        val result = StringBuilder()
        var currentPtr = ptr
        while (true) {
            val b = memory.read(currentPtr).toInt()
            if (b == 0) break
            result.append(b.toChar())
            currentPtr++
        }

        return result.toString()
    }
}
