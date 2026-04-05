import os
import jwt
import requests
import logging
import time
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

logger = logging.getLogger("mecris.auth")

# Configure OIDC/Pocket ID discovery
POCKET_ID_URL = os.getenv("POCKET_ID_AUTH_ENDPOINT", "https://metnoom.urmanac.com")

security = HTTPBearer(auto_error=False)

# Module-level JWKS client — lazily initialized, can be patched in tests
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_uri = os.getenv("OIDC_JWKS_URI", f"{POCKET_ID_URL}/.well-known/jwks.json")
        _jwks_client = PyJWKClient(jwks_uri, lifespan=300)
    return _jwks_client


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify the JWT token from Pocket ID.
    In standalone mode: relaxed check (expiry only, no signature verification).
    In cloud mode: full RSA signature verification via JWKS endpoint.
    """
    if not token:
        return {}
    try:
        if is_standalone_mode():
            # Standalone: decode without signature verification, check expiry only
            unverified = jwt.decode(token, options={"verify_signature": False})
            if unverified.get("exp") and unverified.get("exp") < time.time():
                raise HTTPException(status_code=401, detail="Token has expired")
            return unverified

        # Cloud mode: full JWKS signature verification
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        expected_issuer = os.getenv("OIDC_ISSUER", POCKET_ID_URL)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        if payload.get("iss") != expected_issuer:
            raise HTTPException(status_code=401, detail="Token issuer mismatch")

        return payload

    except HTTPException:
        raise
    except jwt.PyJWTError as e:
        logger.error(f"JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Optional[str]:
    """
    FastAPI dependency to extract and verify the user ID (sub) from the Bearer token.
    Returns None if no token is provided.
    """
    if not credentials:
        return None

    token = credentials.credentials
    payload = verify_token(token)

    user_id = payload.get("sub")
    return user_id


def is_standalone_mode() -> bool:
    """Check if we are running in standalone/local mode where auth might be optional."""
    mode = os.getenv("MECRIS_MODE", "standalone")
    import sys
    print(f"DEBUG AUTH: mode={mode}", file=sys.stderr)
    return mode == "standalone"
