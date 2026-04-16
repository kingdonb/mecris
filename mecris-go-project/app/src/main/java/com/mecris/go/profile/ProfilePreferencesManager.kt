package com.mecris.go.profile

import android.content.Context

private const val PREFS_NAME = "mecris_app_prefs"
private const val KEY_PREFERRED_HEALTH_SOURCE = "preferred_health_source"
private const val KEY_PHONE_NUMBER = "phone_number"
private const val KEY_BEEMINDER_USER = "beeminder_user"

class ProfilePreferencesManager(private val context: Context) {

    private val prefs by lazy {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    fun getPreferredHealthSource(): String? = prefs.getString(KEY_PREFERRED_HEALTH_SOURCE, null)

    fun setPreferredHealthSource(value: String) {
        val trimmed = value.trim()
        prefs.edit().apply {
            if (trimmed.isBlank()) remove(KEY_PREFERRED_HEALTH_SOURCE) else putString(KEY_PREFERRED_HEALTH_SOURCE, trimmed)
            apply()
        }
    }

    fun getPhoneNumber(): String? = prefs.getString(KEY_PHONE_NUMBER, null)

    fun setPhoneNumber(value: String) {
        val trimmed = value.trim()
        prefs.edit().apply {
            if (trimmed.isBlank()) remove(KEY_PHONE_NUMBER) else putString(KEY_PHONE_NUMBER, trimmed)
            apply()
        }
    }

    fun getBeeminderUser(): String? = prefs.getString(KEY_BEEMINDER_USER, null)

    fun setBeeminderUser(value: String) {
        val trimmed = value.trim()
        prefs.edit().apply {
            if (trimmed.isBlank()) remove(KEY_BEEMINDER_USER) else putString(KEY_BEEMINDER_USER, trimmed)
            apply()
        }
    }
}
