import secrets
import base64
import hashlib
import os
import requests
from typing import Tuple, Dict, Any
from urllib.parse import urlencode

# OIDC Configuration Defaults
DEFAULT_AUTH_ENDPOINT = "https://metnoom.urmanac.com/authorize"
DEFAULT_TOKEN_ENDPOINT = "https://metnoom.urmanac.com/api/oidc/token"
DEFAULT_SCOPES = "openid profile email offline_access"

def generate_code_verifier() -> str:
    """
    Generate a PKCE-compliant code verifier.
    A high-entropy cryptographic random string using unreserved characters.
    """
    return secrets.token_urlsafe(32)

def generate_code_challenge(verifier: str) -> str:
    """
    Generate a PKCE-compliant code challenge from a verifier.
    S256 challenge = base64url(sha256(verifier))
    """
    sha256_hash = hashlib.sha256(verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(sha256_hash).decode('utf-8').replace('=', '')

def generate_state() -> str:
    """Generate a cryptographically secure random state string."""
    return secrets.token_urlsafe(16)

def generate_pkce_pair() -> Tuple[str, str]:
    """Generate a (verifier, challenge) pair for PKCE."""
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    return verifier, challenge

def get_redirect_port() -> int:
    """Extract the port from POCKET_ID_REDIRECT_URI or return 0 for random."""
    env_uri = os.getenv("POCKET_ID_REDIRECT_URI")
    if env_uri:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(env_uri)
            if parsed.port:
                return int(parsed.port)
        except Exception:
            pass
    return 0

def get_redirect_uri(port: int) -> str:
    """Determine the redirect URI to use, prioritizing the environment variable."""
    env_uri = os.getenv("POCKET_ID_REDIRECT_URI")
    if env_uri:
        return env_uri
    return f"http://localhost:{port}"

def build_auth_url(challenge: str, state: str, port: int) -> str:
    """Build the authorization URL for PKCE flow."""
    base_url = os.getenv("POCKET_ID_AUTH_ENDPOINT", DEFAULT_AUTH_ENDPOINT)
    client_id = os.getenv("POCKET_ID_CLIENT_ID", "21f65a91-c4df-468d-a256-3b66a54c6d5f")
    redirect_uri = get_redirect_uri(port)
    
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": DEFAULT_SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state
    }
    
    return f"{base_url}?{urlencode(params)}"

def exchange_code_for_tokens(code: str, verifier: str, port: int) -> Dict[str, Any]:
    """Exchange authorization code for tokens using PKCE."""
    token_url = os.getenv("POCKET_ID_TOKEN_ENDPOINT", DEFAULT_TOKEN_ENDPOINT)
    client_id = os.getenv("POCKET_ID_CLIENT_ID", "21f65a91-c4df-468d-a256-3b66a54c6d5f")
    redirect_uri = get_redirect_uri(port)

    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": redirect_uri
    }

    resp = requests.post(token_url, data=data, timeout=(3.0, 10.0))
    resp.raise_for_status()
    return resp.json()

def exchange_refresh_token(refresh_token: str) -> Dict[str, Any]:
    """Exchange a refresh token for new tokens."""
    token_url = os.getenv("POCKET_ID_TOKEN_ENDPOINT", DEFAULT_TOKEN_ENDPOINT)
    client_id = os.getenv("POCKET_ID_CLIENT_ID", "21f65a91-c4df-468d-a256-3b66a54c6d5f")

    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }

    resp = requests.post(token_url, data=data, timeout=(3.0, 10.0))
    resp.raise_for_status()
    return resp.json()
