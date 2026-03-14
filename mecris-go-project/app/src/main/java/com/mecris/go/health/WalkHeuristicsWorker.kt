package com.mecris.go.health

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

class WalkHeuristicsWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
        Log.d("WalkHeuristicsWorker", "Running background walk check...")
        
        val healthManager = HealthConnectManager(applicationContext)
        
        // Use the updated permission check methods
        if (!healthManager.hasForegroundPermissions() || !healthManager.hasBackgroundPermission()) {
            Log.e("WalkHeuristicsWorker", "Missing required Health Connect permissions (Foreground or Background)")
            return Result.failure()
        }

        try {
            val summary = healthManager.fetchRecentWalkData()
            Log.d("WalkHeuristicsWorker", "Walk Inferred: ${summary.isWalkInferred} (Steps: ${summary.totalSteps})")
            
            if (summary.isWalkInferred) {
                val prefs = applicationContext.getSharedPreferences("mecris_go_prefs", Context.MODE_PRIVATE)
                prefs.edit().putBoolean("walk_inferred_today", true).apply()
            }
            
            return Result.success()
        } catch (e: Exception) {
            Log.e("WalkHeuristicsWorker", "Error fetching health data", e)
            return Result.retry()
        }
    }
}
