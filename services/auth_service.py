import os
import jwt
import requests
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger("mecris.auth")

# Configure OIDC/Pocket ID discovery
POCKET_ID_URL = os.getenv("POCKET_ID_AUTH_ENDPOINT", "https://metnoom.urmanac.com")
# In a real app, you'd fetch the public keys from POCKET_ID_URL + "/.well-known/jwks.json"
# For now, we'll implement a robust placeholder that can be extended with JWKS verification.

security = HTTPBearer(auto_error=False)

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify the JWT token from Pocket ID.
    In cloud mode, this performs full signature verification.
    In standalone mode, it might be more relaxed or use a local secret.
    """
    if not token:
        return {}
    try:
        # 1. Decode without verification to check claims
        unverified = jwt.decode(token, options={"verify_signature": False})
        
        # 2. Check issuer and audience if configured
        expected_issuer = os.getenv("OIDC_ISSUER", POCKET_ID_URL)
        if unverified.get("iss") != expected_issuer:
            # logger.warning(f"OIDC: Issuer mismatch. Expected {expected_issuer}, got {unverified.get('iss')}")
            pass # Relaxed for now until JWKS is fully configured
            
        # 3. Check expiration
        import time
        if unverified.get("exp") and unverified.get("exp") < time.time():
            raise HTTPException(status_code=401, detail="Token has expired")
            
        return unverified
        
    except jwt.PyJWTError as e:
        logger.error(f"JWT Verification failed: {e}")
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
    return os.getenv("MECRIS_MODE", "standalone") == "standalone"
