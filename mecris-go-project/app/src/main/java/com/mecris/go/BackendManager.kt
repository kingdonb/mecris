package com.mecris.go

import android.content.Context
import android.content.SharedPreferences

object BackendManager {
    private const val PREFS_NAME = "mecris_backend_prefs"
    private const val KEY_BACKEND_URL = "backend_url"
    private const val AKAMAI_URL = "https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app/"

    val ENDPOINTS = listOf(
        "Local (Emulator)" to "http://10.0.2.2:3000/",
        "Local (LAN: 10.17.14.155)" to "http://10.17.14.155:3000/",
        "Local (Python: 8080)" to "http://10.17.14.155:8080/",
        "Tailnet (Tailscale)" to "http://100.64.0.5:3000/",
        "Akamai Cloud" to AKAMAI_URL
    )

    /** Fresh installs talk to the cloud, not a LAN host that only exists at home. */
    const val DEFAULT_URL = AKAMAI_URL

    /** The URL to use given what the picker stored (null on a fresh install). Pure. */
    fun resolveBaseUrl(stored: String?): String = when {
        stored.isNullOrBlank() -> DEFAULT_URL
        // Fermyon Cloud was deprovisioned; a phone still pointed at it moves to Akamai.
        stored.contains(".fermyon.app", ignoreCase = true) -> DEFAULT_URL
        else -> stored
    }

    fun getBaseUrl(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return resolveBaseUrl(prefs.getString(KEY_BACKEND_URL, null))
    }

    fun setBaseUrl(context: Context, url: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_BACKEND_URL, url).apply()
    }
}
