import secrets
import base64
import hashlib
from typing import Tuple

def generate_code_verifier() -> str:
    """
    Generate a PKCE-compliant code verifier.
    A high-entropy cryptographic random string using unreserved characters.
    """
    # 32 bytes of entropy results in 43 characters after base64url encoding
    return secrets.token_urlsafe(32)

def generate_code_challenge(verifier: str) -> str:
    """
    Generate a PKCE-compliant code challenge from a verifier.
    S256 challenge = base64url(sha256(verifier))
    """
    sha256_hash = hashlib.sha256(verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(sha256_hash).decode('utf-8').replace('=', '')

def generate_pkce_pair() -> Tuple[str, str]:
    """Generate a (verifier, challenge) pair for PKCE."""
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    return verifier, challenge
