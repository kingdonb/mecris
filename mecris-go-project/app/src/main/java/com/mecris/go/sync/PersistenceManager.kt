package com.mecris.go.sync

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.mecris.go.health.WalkDataSummary
import java.time.Instant

data class DashboardCache(
    val walkData: WalkDataSummary?,
    val budgetAmount: Double?,
    val languageStats: List<LanguageStatDto>,
    val homeServerActive: Boolean?,
    val lastSyncTime: String,
    val lastUpdatedMillis: Long = System.currentTimeMillis()
)

class PersistenceManager(context: Context) {
    private val prefs = context.getSharedPreferences("mecris_dashboard_cache", Context.MODE_PRIVATE)
    private val gson = Gson()

    fun saveDashboard(cache: DashboardCache) {
        val json = gson.toJson(cache)
        prefs.edit().putString("dashboard_data", json).apply()
    }

    fun loadDashboard(): DashboardCache? {
        val json = prefs.getString("dashboard_data", null) ?: return null
        return try {
            gson.fromJson(json, DashboardCache::class.java)
        } catch (e: Exception) {
            null
        }
    }

    fun isCacheStale(timeoutMinutes: Long = 5): Boolean {
        val json = prefs.getString("dashboard_data", null) ?: return true
        return try {
            val cache = gson.fromJson(json, DashboardCache::class.java)
            val now = System.currentTimeMillis()
            val diff = now - cache.lastUpdatedMillis
            diff > (timeoutMinutes * 60 * 1000)
        } catch (e: Exception) {
            true
        }
    }
}
