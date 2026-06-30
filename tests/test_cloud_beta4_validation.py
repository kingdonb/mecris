import pytest
import httpx
import os

# Target URLs
LOCAL_URL = "http://localhost:3000"
FERMYON_URL = "https://mecris-sync-v2-r0r86pso.fermyon.app"
AKAMAI_URL = "https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app"

@pytest.mark.asyncio
async def test_fermyon_review_pump_not_implemented():
    """Verify Fermyon Cloud returns NotImplementedError or 404 (disabled) for SDK v4 binaries."""
    async with httpx.AsyncClient() as client:
        url = f"{FERMYON_URL}/internal/review-pump-status-py"
        try:
            resp = await client.post(
                url, 
                json={"debt": 0, "tomorrow_liability": 0, "daily_completions": 0, "multiplier_x10": 10},
                timeout=10.0
            )
            # We expect a 500 for NotImplementedError or 404 if the route is fully disabled
            assert resp.status_code in [404, 500]
            if resp.status_code == 500:
                assert "NotImplementedError" in resp.text
            print(f"\n[Verified] Fermyon Review Pump: {resp.status_code} - {resp.text[:50]}...")
        except Exception as e:
            pytest.fail(f"Fermyon request failed: {e}")

@pytest.mark.asyncio
async def test_akamai_health_500():
    """Verify Akamai Health returns 500 (current quantified failure)."""
    async with httpx.AsyncClient() as client:
        url = f"{AKAMAI_URL}/health"
        try:
            resp = await client.get(url, timeout=10.0)
            assert resp.status_code == 500
            print(f"\n[Verified] Akamai Health: {resp.status_code}")
        except Exception as e:
            pytest.fail(f"Akamai request failed: {e}")

@pytest.mark.asyncio
async def test_local_health_200():
    """Verify Local Health returns 200 (sanity check)."""
    # This requires 'spin up' to be running locally.
    try:
        async with httpx.AsyncClient() as client:
            url = f"{LOCAL_URL}/health"
            resp = await client.get(
                url, 
                headers={"Authorization": "Bearer TestUser c0a81a4b-115a-4eb6-bc2c-40908c58bf64"}, 
                timeout=2.0
            )
            assert resp.status_code == 200
            print(f"\n[Verified] Local Health: {resp.status_code}")
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip("Local spin server not running")

@pytest.mark.asyncio
async def test_akamai_sync_not_found():
    """Verify Akamai Sync endpoint (quantifying if it's 500 or 404/Not Found)."""
    async with httpx.AsyncClient() as client:
        url = f"{AKAMAI_URL}/internal/cloud-sync"
        try:
            resp = await client.post(url, timeout=10.0)
            # If the guest isn't invoked, it might be 500.
            # If the route is missing, it might be 404.
            print(f"\n[Quantify] Akamai Sync: {resp.status_code}")
            assert resp.status_code in [500, 404]
        except Exception as e:
            pytest.fail(f"Akamai Sync request failed: {e}")
