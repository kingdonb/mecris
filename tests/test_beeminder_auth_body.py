import os
import httpx
import pytest
import asyncio
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.asyncio
async def test_beeminder_post_auth_methods():
    token = os.getenv("BEEMINDER_AUTH_TOKEN")
    user = os.getenv("BEEMINDER_USERNAME")
    goal = "bike"
    
    if not token or not user:
        pytest.skip("BEEMINDER_AUTH_TOKEN or BEEMINDER_USERNAME not set")

    url = f"https://www.beeminder.com/api/v1/users/{user}/goals/{goal}/datapoints.json"
    
    async with httpx.AsyncClient() as client:
        # We expect auth_token only to work (200)
        resp = await client.post(url, data={
            "auth_token": token,
            "value": 0,
            "comment": "TDG Test: auth_token only"
        })
        assert resp.status_code == 200, f"Expected 200 for auth_token only, got {resp.status_code}"

        # We expect both to FAIL (401) - this reproduces the bug!
        resp = await client.post(url, data={
            "access_token": token,
            "auth_token": token,
            "value": 0,
            "comment": "TDG Test: both"
        })
        assert resp.status_code == 401, f"Expected 401 for both (confirming Beeminder quirk), got {resp.status_code}"


if __name__ == "__main__":
    asyncio.run(test_beeminder_post_auth_methods())
