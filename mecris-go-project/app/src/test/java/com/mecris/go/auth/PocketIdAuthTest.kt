package com.mecris.go.auth

import android.content.Context
import android.content.SharedPreferences
import android.net.Uri
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
    private val authService = mockk<AuthorizationService>(relaxed = true)

    @Before
    fun setup() {
        mockkStatic(Uri::class)
        every { Uri.parse(any()) } returns mockk(relaxed = true)
        
        every { context.getSharedPreferences("auth_prefs", Context.MODE_PRIVATE) } returns sharedPrefs
        every { sharedPrefs.getString("auth_state_json", null) } returns null
        every { sharedPrefs.edit() } returns prefsEditor
        every { prefsEditor.remove(any()) } returns prefsEditor
        every { prefsEditor.putString(any(), any()) } returns prefsEditor
        every { prefsEditor.clear() } returns prefsEditor
    }

    @After
    fun teardown() {
        unmockkStatic(Uri::class)
    }

    @Test
    fun `signOut clears auth token from SharedPreferences and resets state to Idle`() {
        val auth = PocketIdAuth(context, authService)
        auth.signOut()
        verify { prefsEditor.clear() }
        verify { prefsEditor.apply() }
        assertEquals(AuthState.Idle, auth.authState.value)
    }
}
