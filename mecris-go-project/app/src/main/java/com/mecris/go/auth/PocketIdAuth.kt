package com.mecris.go.auth

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.result.ActivityResultLauncher
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import net.openid.appauth.*

class PocketIdAuth(private val context: Context) {

    private val authService: AuthorizationService = AuthorizationService(context)
    
    // Replace with your actual Pocket ID domain
    private val authEndpoint = Uri.parse("https://metnoom.urmanac.com/authorize")
    private val tokenEndpoint = Uri.parse("https://metnoom.urmanac.com/api/oidc/token")
    
    // Replace with your actual Client ID from the Pocket ID admin panel
    private val clientId = "REPLACE_WITH_YOUR_CLIENT_ID"
    
    private val redirectUri = Uri.parse("com.mecris.go:/oauth2redirect")

    private val _authState = MutableStateFlow<AuthState>(AuthState.Idle)
    val authState: StateFlow<AuthState> = _authState

    // The persistent AuthState object from AppAuth
    private var internalAuthState: net.openid.appauth.AuthState = net.openid.appauth.AuthState()

    fun authenticateWithPasskey(launcher: ActivityResultLauncher<Intent>) {
        _authState.value = AuthState.Loading
        
        val serviceConfig = AuthorizationServiceConfiguration(authEndpoint, tokenEndpoint)
        
        val authRequest = AuthorizationRequest.Builder(
            serviceConfig,
            clientId,
            ResponseTypeValues.CODE,
            redirectUri
        )
        .setScopes(AuthorizationRequest.Scope.OPENID, AuthorizationRequest.Scope.PROFILE, AuthorizationRequest.Scope.EMAIL)
        .build()

        val authIntent = authService.getAuthorizationRequestIntent(authRequest)
        launcher.launch(authIntent)
    }

    fun handleAuthorizationResponse(intent: Intent?) {
        if (intent == null) {
            _authState.value = AuthState.Error("Authorization canceled or failed.")
            return
        }

        val resp = AuthorizationResponse.fromIntent(intent)
        val ex = AuthorizationException.fromIntent(intent)

        internalAuthState.update(resp, ex)

        if (resp != null) {
            // Exchange the authorization code for tokens
            authService.performTokenRequest(resp.createTokenExchangeRequest()) { tokenResponse, tokenException ->
                internalAuthState.update(tokenResponse, tokenException)
                
                if (tokenResponse != null) {
                    val jwt = tokenResponse.accessToken ?: tokenResponse.idToken
                    if (jwt != null) {
                        _authState.value = AuthState.Authenticated(jwt)
                    } else {
                        _authState.value = AuthState.Error("No access token received.")
                    }
                } else {
                    _authState.value = AuthState.Error("Token exchange failed: ${tokenException?.message}")
                }
            }
        } else {
            _authState.value = AuthState.Error("Authorization failed: ${ex?.message}")
        }
    }
    
    fun getValidAccessToken(callback: (String?) -> Unit) {
        internalAuthState.performActionWithFreshTokens(authService) { accessToken, _, ex ->
            if (ex != null) {
                _authState.value = AuthState.Error("Token refresh failed: ${ex.message}")
                callback(null)
            } else {
                callback(accessToken)
            }
        }
    }

    fun dispose() {
        authService.dispose()
    }
}

sealed class AuthState {
    object Idle : AuthState()
    object Loading : AuthState()
    data class Authenticated(val jwt: String) : AuthState()
    data class Error(val message: String) : AuthState()
}
