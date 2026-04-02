#!/usr/bin/env python3
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from beeminder_client import BeeminderClient
from scripts.clozemaster_scraper import ClozemasterScraper

async def sanity_check():
    load_dotenv()
    user_id = os.getenv("DEFAULT_USER_ID")
    
    print(f"🧐 Sanity checking multi-tenant credential loading for {user_id}...")
    
    # 1. Check BeeminderClient
    print("\n--- Beeminder ---")
    bc = BeeminderClient(user_id=user_id)
    await bc._load_credentials()
    if bc.username and bc.auth_token:
        print(f"✅ Beeminder username loaded: {bc.username}")
        print(f"✅ Beeminder token decrypted successfully (len: {len(bc.auth_token)})")
    else:
        print("❌ Beeminder credentials failed to load")

    # 2. Check ClozemasterScraper
    print("\n--- Clozemaster ---")
    cs = ClozemasterScraper(user_id=user_id)
    await cs._load_credentials()
    if cs.email and cs.password:
        print(f"✅ Clozemaster email loaded: {cs.email}")
        print(f"✅ Clozemaster password decrypted successfully (len: {len(cs.password)})")
    else:
        print("❌ Clozemaster credentials failed to load")

if __name__ == "__main__":
    asyncio.run(sanity_check())
