package com.mecris.go.profile

import android.content.Context

private const val PREFS_NAME = "mecris_app_prefs"
private const val KEY_PREFERRED_HEALTH_SOURCE = "preferred_health_source"
private const val KEY_PHONE_NUMBER = "phone_number"
private const val KEY_BEEMINDER_USER = "beeminder_user"
private const val KEY_LATITUDE = "location_lat"
private const val KEY_LONGITUDE = "location_lon"
private const val KEY_VACATION_MODE_UNTIL = "vacation_mode_until"
private const val KEY_AUTONOMOUS_SYNC_ENABLED = "autonomous_sync_enabled"

class ProfilePreferencesManager(private val context: Context) {

    private val prefs by lazy {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    fun getPreferredHealthSource(): String? = prefs.getString(KEY_PREFERRED_HEALTH_SOURCE, null)

    fun setPreferredHealthSource(value: String) {
        val trimmed = value.trim()
        prefs.edit().apply {
            if (trimmed.isBlank()) remove(KEY_PREFERRED_HEALTH_SOURCE) else putString(KEY_PREFERRED_HEALTH_SOURCE, trimmed)
            commit()
        }
    }

    fun getPhoneNumber(): String? = prefs.getString(KEY_PHONE_NUMBER, null)

    fun setPhoneNumber(value: String) {
        val trimmed = value.trim()
        prefs.edit().apply {
            if (trimmed.isBlank()) remove(KEY_PHONE_NUMBER) else putString(KEY_PHONE_NUMBER, trimmed)
            commit()
        }
    }

    fun getBeeminderUser(): String? = prefs.getString(KEY_BEEMINDER_USER, null)

    fun setBeeminderUser(value: String) {
        val trimmed = value.trim()
        prefs.edit().apply {
            if (trimmed.isBlank()) remove(KEY_BEEMINDER_USER) else putString(KEY_BEEMINDER_USER, trimmed)
            commit()
        }
    }

    fun getLatitude(): String? = prefs.getString(KEY_LATITUDE, null)
    fun setLatitude(value: String) {
        prefs.edit().putString(KEY_LATITUDE, value.trim()).commit()
    }

    fun getLongitude(): String? = prefs.getString(KEY_LONGITUDE, null)
    fun setLongitude(value: String) {
        prefs.edit().putString(KEY_LONGITUDE, value.trim()).commit()
    }

    fun getVacationModeUntil(): String? = prefs.getString(KEY_VACATION_MODE_UNTIL, null)
    fun setVacationModeUntil(value: String?) {
        prefs.edit().putString(KEY_VACATION_MODE_UNTIL, value?.trim()).commit()
    }

    fun isAutonomousSyncEnabled(): Boolean = prefs.getBoolean(KEY_AUTONOMOUS_SYNC_ENABLED, false)
    fun setAutonomousSyncEnabled(value: Boolean) {
        prefs.edit().putBoolean(KEY_AUTONOMOUS_SYNC_ENABLED, value).commit()
    }

    fun clearAll() {
        prefs.edit().clear().commit()
    }
}
