package com.mecris.go.ai

import android.content.Context
import android.util.Log
import com.google.ai.edge.aicore.GenerativeModel
import com.google.ai.edge.aicore.generationConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * SovereignBrain: Local LLM inference engine for intelligent accountability.
 * Uses Google AI Edge SDK to tap into on-device Gemini Nano via AICore.
 */
class SovereignBrain(private val context: Context) {

    companion object {
        fun goalSpecificFallback(targetGoal: String): String = when (targetGoal.uppercase()) {
            "ARABIC" -> "Your Arabic cards won't review themselves. Time to do the work."
            "WALK" -> "Time for a walk. Your physical goal is waiting."
            "GREEK" -> "The moussaka is waiting. Do your cards."
            else -> "Your goal is waiting. Time to make progress."
        }
    }

    private var generativeModel: GenerativeModel? = null

    private fun setupLlm(): Boolean {
        if (generativeModel != null) return true

        return try {
            // Using the Kotlin DSL for GenerationConfig as per experimental SDK docs
            val config = generationConfig {
                context = this@SovereignBrain.context
                temperature = 0.7f
                topK = 40
                maxOutputTokens = 512
            }

            generativeModel = GenerativeModel(generationConfig = config)
            true
        } catch (e: Exception) {
            Log.e("SovereignBrain", "AICore initialization failed: ${e.message}")
            false
        }
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
        if (!setupLlm()) return@withContext null
        val model = generativeModel ?: return@withContext null

        val prompt = """
            You are Mecris, a clever, observant, and slightly sassy personal accountability partner.
            Context:
            - Goal: $targetGoal
            - Sensitive Mode: $isSensitive
            - Weather: ${weatherConditions ?: "Unknown"}
            - Is Dark: $isDark
            
            Instruction: Write a one-sentence motivating notification to push the user to complete their goal. 
            Be clever and firm, but avoid overly affectionate terms.
            ${if (isSensitive) "Do NOT mention dogs (Boris or Fiona)." else "You can mention Boris and Fiona the dogs as motivation."}
            
            Response:
        """.trimIndent()

        try {
            val response = model.generateContent(prompt)
            val nagText = response.text ?: goalSpecificFallback(targetGoal)
            NarrativeResult(nagText.trim(), prompt)
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
