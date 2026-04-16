"""
E2E Validation for Akamai Cron Triggers Security (#185).
This test verifies that the /internal/* endpoints require authentication.
"""
import httpx
import pytest

AKAMAI_BASE_URL = "https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app"

@pytest.mark.asyncio
async def test_akamai_endpoints_require_auth():
    """Unauthenticated requests to /internal/* endpoints should return 401."""
    
    endpoints = [
        "/internal/failover-sync",
        "/internal/trigger-reminders"
    ]
    
    async with httpx.AsyncClient() as client:
        for endpoint in endpoints:
            url = f"{AKAMAI_BASE_URL}{endpoint}"
            response = await client.post(url, timeout=30.0)
            
            # We expect a 401 Unauthorized when no secret is provided
            assert response.status_code == 401, f"{endpoint} returned {response.status_code} instead of 401"
