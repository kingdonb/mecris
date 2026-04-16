"""
E2E Validation for Akamai Cron Triggers (#183).
This test hits the live Akamai endpoint and verifies side effects in Neon.
"""
import os
import httpx
import pytest
import psycopg2
from datetime import datetime, timezone

AKAMAI_BASE_URL = "https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app"
DEFAULT_USER_ID = "c0a81a4b-115a-4eb6-bc2c-40908c58bf64"

def get_last_updated(language):
    db_url = os.getenv("NEON_DB_URL")
    if not db_url:
        pytest.skip("NEON_DB_URL not set")
    if "localhost" in db_url or "127.0.0.1" in db_url:
        pytest.skip("NEON_DB_URL is local postgres — live E2E test skipped in CI")
    
    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_updated FROM language_stats WHERE user_id = %s AND language_name = %s",
                (DEFAULT_USER_ID, language.upper())
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()

@pytest.mark.asyncio
async def test_akamai_failover_sync_side_effect():
    """Trigger /internal/failover-sync on Akamai and verify language_stats update."""
    # 1. Get current state
    start_time = datetime.now(timezone.utc)
    old_update = get_last_updated("ARABIC")
    print(f"Old update: {old_update}")

    # 2. Trigger Akamai
    url = f"{AKAMAI_BASE_URL}/internal/failover-sync"
    async with httpx.AsyncClient() as client:
        # The endpoint expects POST
        response = await client.post(url, timeout=30.0)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    # 3. Verify side effect in Neon
    new_update = get_last_updated("ARABIC")
    print(f"New update: {new_update}")
    
    assert new_update is not None
    # Depending on DB precision and clock skew, we just want it to be recent or newer than old_update
    if old_update:
        assert new_update > old_update
    else:
        assert new_update > start_time # If it was None before
