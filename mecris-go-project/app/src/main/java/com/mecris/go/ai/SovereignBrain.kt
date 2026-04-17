package com.mecris.go.ai

import android.content.Context
import android.util.Log
import com.google.mediapipe.tasks.genai.llminference.LlmInference
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/**
 * SovereignBrain: Local LLM inference engine for intelligent accountability.
 * Uses MediaPipe LLM Inference API to run Gemma-2b on-device.
 */
class SovereignBrain(private val context: Context) {

    private var llmInference: LlmInference? = null

    companion object {
        private const val MODEL_PATH = "/data/local/tmp/gemma-2b-it-cpu-int4.bin"
    }

    private fun setupLlm() {
        if (llmInference != null) return

        val modelFile = File(MODEL_PATH)
        if (!modelFile.exists()) {
            Log.w("SovereignBrain", "LLM Model not found at $MODEL_PATH.")
            return
        }

        val options = LlmInference.LlmInferenceOptions.builder()
            .setModelPath(MODEL_PATH)
            .setMaxTokens(512)
            .setTopK(40)
            .setTemperature(0.7f)
            .setRandomSeed(101)
            .build()

        llmInference = LlmInference.createFromOptions(context, options)
    }

    /**
     * Diagnostic result containing the nag and the prompt used.
     */
    data class NarrativeResult(val nag: String, val prompt: String)

    /**
     * Generates a sassy, context-aware notification message with diagnostic data.
     */
    suspend fun generateWithContext(
        targetGoal: String,
        isSensitive: Boolean,
        weatherConditions: String?,
        isDark: Boolean = false
    ): NarrativeResult? = withContext(Dispatchers.Default) {
        setupLlm()
        val llm = llmInference ?: return@withContext null

        val prompt = """
            You are Mecris, a sassy but supportive personal accountability partner.
            Context:
            - Goal: $targetGoal
            - Sensitive Mode: $isSensitive
            - Weather: ${weatherConditions ?: "Unknown"}
            - Is Dark: $isDark
            
            Instruction: Write a one-sentence sassy notification to push the user to complete their goal.
            ${if (isSensitive) "Do NOT mention dogs (Boris or Fiona)." else "Feel free to mention Boris and Fiona the dogs."}
            
            Response:
        """.trimIndent()

        try {
            val response = llm.generateResponse(prompt)
            NarrativeResult(response.trim(), prompt)
        } catch (e: Exception) {
            Log.e("SovereignBrain", "LLM Inference failed: ${e.message}")
            null
        }
    }

    suspend fun generateNarrativeDirective(
        targetGoal: String,
        isSensitive: Boolean,
        weatherConditions: String?,
        isDark: Boolean = false
    ): String? {
        return generateWithContext(targetGoal, isSensitive, weatherConditions, isDark)?.nag
    }
}
