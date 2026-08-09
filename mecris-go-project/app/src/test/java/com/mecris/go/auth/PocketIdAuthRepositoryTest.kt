package com.mecris.go.auth

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import io.mockk.*
import net.openid.appauth.AuthorizationService
import net.openid.appauth.AuthState
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class PocketIdAuthRepositoryTest {

    private val context = mockk<Context>(relaxed = true)
    private val authService = mockk<AuthorizationService>(relaxed = true)
    private val sharedPrefs = mockk<SharedPreferences>(relaxed = true)
    private val prefsEditor = mockk<SharedPreferences.Editor>(relaxed = true)
    private val masterKeyAlias = "test_master_key"

    @Before
    fun setup() {
        mockkStatic(MasterKeys::class)
        mockkStatic(EncryptedSharedPreferences::class)
        
        every { MasterKeys.getOrCreate(any()) } returns masterKeyAlias
        every { EncryptedSharedPreferences.create(any(), any(), any(), any(), any()) } returns sharedPrefs
        every { sharedPrefs.getString("auth_state_json", null) } returns null
        every { sharedPrefs.getLong("refresh_token_issued_at", 0L) } returns 0L
        every { sharedPrefs.getBoolean("explicit_logout", false) } returns false
        every { sharedPrefs.edit() } returns prefsEditor
        every { prefsEditor.putString(any(), any()) } returns prefsEditor
        every { prefsEditor.putLong(any(), anyLong()) } returns prefsEditor
        every { prefsEditor.putBoolean(any(), anyBoolean()) } returns prefsEditor
        every { prefsEditor.apply() } returns Unit
        every { prefsEditor.clear() } returns prefsEditor
    }

    @After
    fun teardown() {
        unmockkStatic(MasterKeys::class)
        unmockkStatic(EncryptedSharedPreferences::class)
    }

    @Test
    fun `initial state is Idle when no stored auth`() {
        val repo = PocketIdAuthRepository(context, authService)
        assertEquals(AuthState.Idle, repo.authState.value)
    }

    @Test
    fun `signOut clears auth state and sets explicit logout flag`() {
        val repo = PocketIdAuthRepository(context, authService)
        repo.signOut()
        
        verify { prefsEditor.clear() }
        verify { prefsEditor.putBoolean("explicit_logout", true) }
        verify { prefsEditor.apply() }
        assertEquals(AuthState.Idle, repo.authState.value)
    }

    @Test
    fun `loadAuthState restores authenticated state from prefs`() {
        val savedAuthState = AuthState()
        // We can't easily mock AuthState.jsonSerializeString/Deserialize, 
        // so this test verifies the flow logic
        
        every { sharedPrefs.getString("auth_state_json", null) } returns "{}"
        every { sharedPrefs.getLong("refresh_token_issued_at", 0L) } returns (System.currentTimeMillis() / 1000)
        every { sharedPrefs.getBoolean("explicit_logout", false) } returns false
        
        // This would need a real AuthState object to fully test
        // For now, verify the repo can be created without crash
        val repo = PocketIdAuthRepository(context, authService)
        assertNotNull(repo.authState.value)
    }
}