package com.mecris.go

import android.content.Context
import android.content.SharedPreferences

object BackendManager {
    private const val PREFS_NAME = "mecris_backend_prefs"
    private const val KEY_BACKEND_URL = "backend_url"

    val ENDPOINTS = listOf(
        "Local (Emulator)" to "http://10.0.2.2:3000/",
        "Local (LAN: 10.17.14.155)" to "http://10.17.14.155:3000/",
        "Tailnet (Tailscale)" to "http://100.64.0.5:3000/",
        "Akamai Cloud" to "https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/",
        "Fermyon Cloud" to "https://mecris-sync-v2-glo0zpfm.fermyon.app/"
    )

    fun getBaseUrl(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getString(KEY_BACKEND_URL, ENDPOINTS[1].second) ?: ENDPOINTS[1].second
    }

    fun setBaseUrl(context: Context, url: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_BACKEND_URL, url).apply()
    }
}
