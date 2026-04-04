import secrets
import base64
import hashlib

def generate_code_verifier() -> str:
    """
    Generate a PKCE-compliant code verifier.
    A high-entropy cryptographic random string using unreserved characters.
    """
    # 32 bytes of entropy results in 43 characters after base64url encoding
    token = secrets.token_urlsafe(32)
    return token

def generate_code_challenge(verifier: str) -> str:
    """
    Generate a PKCE-compliant code challenge from a verifier.
    S256 challenge = base64url(sha256(verifier))
    """
    sha256_hash = hashlib.sha256(verifier.encode('utf-8')).digest()
    # base64.urlsafe_b64encode adds padding '=' which must be removed for PKCE
    challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8').replace('=', '')
    return challenge
