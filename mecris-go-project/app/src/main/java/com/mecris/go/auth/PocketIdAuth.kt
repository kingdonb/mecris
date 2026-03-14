package com.mecris.go.auth

import android.content.Context
import androidx.credentials.CredentialManager
import androidx.credentials.GetCredentialRequest
import androidx.credentials.GetPublicKeyCredentialOption
import androidx.credentials.exceptions.GetCredentialException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

class PocketIdAuth(private val context: Context) {

    private val credentialManager = CredentialManager.create(context)

    private val _authState = MutableStateFlow<AuthState>(AuthState.Idle)
    val authState: StateFlow<AuthState> = _authState

    // In a real implementation, this JSON comes from your Pocket ID server's 
    // WebAuthn configuration endpoint (e.g., /webauthn/authenticate)
    private val getPasskeyRequestJson = """
        {
          "challenge": "base64url-encoded-challenge-from-pocket-id",
          "timeout": 60000,
          "rpId": "your-pocket-id.example.com",
          "userVerification": "required"
        }
    """.trimIndent()

    suspend fun authenticateWithPasskey() {
        _authState.value = AuthState.Loading
        try {
            val getPublicKeyCredentialOption = GetPublicKeyCredentialOption(
                requestJson = getPasskeyRequestJson
            )

            val request = GetCredentialRequest(
                listOf(getPublicKeyCredentialOption)
            )

            // This triggers the Android bottom sheet for Passkeys
            val result = credentialManager.getCredential(
                request = request,
                context = context
            )

            val credential = result.credential
            // Normally, we send credential.data to the Pocket ID server here 
            // to exchange for a JWT. For Phase 1 vertical slice, we simulate success.
            
            _authState.value = AuthState.Authenticated("Simulated_JWT_Token_From_PocketID")

        } catch (e: GetCredentialException) {
            _authState.value = AuthState.Error(e.message ?: "Authentication failed")
        } catch (e: Exception) {
            _authState.value = AuthState.Error(e.localizedMessage ?: "Unknown error")
        }
    }
}

sealed class AuthState {
    object Idle : AuthState()
    object Loading : AuthState()
    data class Authenticated(val jwt: String) : AuthState()
    data class Error(val message: String) : AuthState()
}
