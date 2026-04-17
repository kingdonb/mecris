"""
E2E Tests for Phone Verification (#188).
This test uses the auth_bypass mechanism to verify the full SMS verification lifecycle.
"""
import os
import httpx
import pytest
import psycopg2
from datetime import datetime, timezone

# We'll test against the Fermyon Cloud instance or local if available
BASE_URL = "https://mecris-sync-v2-r0r86pso.fermyon.app"
TEST_USER_ID = "c0a81a4b-115a-4eb6-bc2c-40908c58bf64"
AUTH_HEADER = {"Authorization": f"TestUser {TEST_USER_ID}"}

def get_db_connection():
    db_url = os.getenv("NEON_DB_URL")
    if not db_url:
        pytest.skip("NEON_DB_URL not set")
    return psycopg2.connect(db_url)

def reset_verification_status():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET phone_verified = false WHERE pocket_id_sub = %s", (TEST_USER_ID,))
            cur.execute("DELETE FROM phone_verifications WHERE user_id = %s", (TEST_USER_ID,))
            conn.commit()
    finally:
        conn.close()

@pytest.mark.asyncio
async def test_phone_verification_lifecycle():
    """Verify requesting a code and confirming it updates the database."""
    reset_verification_status()
    
    async with httpx.AsyncClient() as client:
        # 1. Request verification
        print("\n[1] Requesting verification...")
        # Use a dummy number that matches Twilio Sandbox or just any valid format
        req_payload = {"phone_number": "+15852378622"}
        response = await client.post(f"{BASE_URL}/internal/request-phone-verification", 
                                    json=req_payload, headers=AUTH_HEADER, timeout=30.0)
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        assert response.json()["status"] == "success"

        # 2. "Backdoor" into DB to get the code_hash (we can't see the code, so we'll have to mock the confirm)
        # Actually, for a TRUE E2E, we need the 6-digit code.
        # Let's check the logs or just verify the hash was created.
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT code_hash, expires_at FROM phone_verifications WHERE user_id = %s", (TEST_USER_ID,))
                row = cur.fetchone()
                assert row is not None, "Verification record not created in DB"
                code_hash = row[0]
                expires_at = row[1]
                print(f"Code Hash found: {code_hash}")
                print(f"Expires at: {expires_at} (Now: {datetime.now(timezone.utc)})")
                
                # Since we can't know the plain code from the hash (easily), 
                # we'll test the confirm endpoint with an INVALID code first.
                print("[2] Testing invalid code...")
                conf_payload = {"code": "000000"}
                conf_resp = await client.post(f"{BASE_URL}/internal/confirm-phone-verification", 
                                             json=conf_payload, headers=AUTH_HEADER, timeout=30.0)
                assert conf_resp.status_code == 401
                assert conf_resp.json()["message"] == "Invalid code"

                # 3. To verify the SUCCESS path, we'll manually update the DB to a known hash
                # Code '123456' -> SHA1: '7c4a8d09ca3762af61e59520943dc26494f8941b'
                known_code = "123456"
                known_hash = "7c4a8d09ca3762af61e59520943dc26494f8941b"
                cur.execute("UPDATE phone_verifications SET code_hash = %s WHERE user_id = %s", (known_hash, TEST_USER_ID))
                conn.commit()
                
                print("[3] Testing valid code (manual hash)...")
                conf_payload = {"code": known_code}
                conf_resp = await client.post(f"{BASE_URL}/internal/confirm-phone-verification", 
                                             json=conf_payload, headers=AUTH_HEADER, timeout=30.0)
                
                assert conf_resp.status_code == 200, f"Confirm failed: {conf_resp.text}"
                assert conf_resp.json()["message"] == "Phone number verified"

                # 4. Final check: User flag
                cur.execute("SELECT phone_verified FROM users WHERE pocket_id_sub = %s", (TEST_USER_ID,))
                assert cur.fetchone()[0] is True, "User flag not updated to true"
                print("SUCCESS: Phone verified flag is TRUE")

        finally:
            conn.close()
