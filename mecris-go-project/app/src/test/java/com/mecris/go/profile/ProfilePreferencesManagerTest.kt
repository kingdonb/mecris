package com.mecris.go.profile

import android.content.Context
import android.content.SharedPreferences
import io.mockk.*
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

class ProfilePreferencesManagerTest {

    private val context = mockk<Context>(relaxed = true)
    private val sharedPrefs = mockk<SharedPreferences>()
    private val prefsEditor = mockk<SharedPreferences.Editor>(relaxed = true)

    @Before
    fun setup() {
        every { context.getSharedPreferences("mecris_app_prefs", Context.MODE_PRIVATE) } returns sharedPrefs
        every { sharedPrefs.edit() } returns prefsEditor
        every { prefsEditor.putString(any(), any()) } returns prefsEditor
        every { prefsEditor.remove(any()) } returns prefsEditor
    }

    @Test
    fun `getPreferredHealthSource returns null when not set`() {
        every { sharedPrefs.getString("preferred_health_source", null) } returns null
        val manager = ProfilePreferencesManager(context)
        assertNull(manager.getPreferredHealthSource())
    }

    @Test
    fun `getPreferredHealthSource returns stored value`() {
        every { sharedPrefs.getString("preferred_health_source", null) } returns "com.google.android.apps.fitness"
        val manager = ProfilePreferencesManager(context)
        assertEquals("com.google.android.apps.fitness", manager.getPreferredHealthSource())
    }

    @Test
    fun `setPreferredHealthSource writes to SharedPreferences`() {
        val manager = ProfilePreferencesManager(context)
        manager.setPreferredHealthSource("com.samsung.health")
        verify { prefsEditor.putString("preferred_health_source", "com.samsung.health") }
        verify { prefsEditor.apply() }
    }

    @Test
    fun `setPreferredHealthSource with blank value removes the key`() {
        val manager = ProfilePreferencesManager(context)
        manager.setPreferredHealthSource("   ")
        verify { prefsEditor.remove("preferred_health_source") }
        verify { prefsEditor.apply() }
    }

    @Test
    fun `getPhoneNumber returns null when not set`() {
        every { sharedPrefs.getString("phone_number", null) } returns null
        val manager = ProfilePreferencesManager(context)
        assertNull(manager.getPhoneNumber())
    }

    @Test
    fun `setPhoneNumber writes to SharedPreferences`() {
        val manager = ProfilePreferencesManager(context)
        manager.setPhoneNumber("+15551234567")
        verify { prefsEditor.putString("phone_number", "+15551234567") }
        verify { prefsEditor.apply() }
    }

    @Test
    fun `getBeeminderUser returns null when not set`() {
        every { sharedPrefs.getString("beeminder_user", null) } returns null
        val manager = ProfilePreferencesManager(context)
        assertNull(manager.getBeeminderUser())
    }

    @Test
    fun `setBeeminderUser writes to SharedPreferences`() {
        val manager = ProfilePreferencesManager(context)
        manager.setBeeminderUser("alice")
        verify { prefsEditor.putString("beeminder_user", "alice") }
        verify { prefsEditor.apply() }
    }
}
