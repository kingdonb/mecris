package com.mecris.go.auth

import android.content.Context
import android.content.SharedPreferences
import io.mockk.*
import net.openid.appauth.AuthorizationService
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

class PocketIdAuthTest {

    private val context = mockk<Context>(relaxed = true)
    private val sharedPrefs = mockk<SharedPreferences>()
    private val prefsEditor = mockk<SharedPreferences.Editor>(relaxed = true)

    @Before
    fun setup() {
        mockkConstructor(AuthorizationService::class)
        every { context.getSharedPreferences("auth_prefs", Context.MODE_PRIVATE) } returns sharedPrefs
        every { sharedPrefs.getString("auth_state_json", null) } returns null
        every { sharedPrefs.edit() } returns prefsEditor
        every { prefsEditor.remove(any()) } returns prefsEditor
        every { prefsEditor.putString(any(), any()) } returns prefsEditor
    }

    @After
    fun teardown() {
        unmockkConstructor(AuthorizationService::class)
    }

    @Test
    fun `signOut clears auth token from SharedPreferences and resets state to Idle`() {
        val auth = PocketIdAuth(context)
        auth.signOut()
        verify { prefsEditor.remove("auth_state_json") }
        verify { prefsEditor.apply() }
        assertEquals(AuthState.Idle, auth.authState.value)
    }
}
