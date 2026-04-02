#!/usr/bin/env python3
"""
Credential Migration Script for Mecris
Moves Clozemaster and Beeminder credentials from .env to encrypted rows in Neon DB.
"""

import os
import sys
import logging
import psycopg2
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.encryption_service import EncryptionService

load_dotenv()
logger = logging.getLogger("mecris.migration")
logging.basicConfig(level=logging.INFO)

def migrate():
    neon_url = os.getenv("NEON_DB_URL")
    master_key = os.getenv("MASTER_ENCRYPTION_KEY")
    user_id = os.getenv("DEFAULT_USER_ID")
    
    if not all([neon_url, master_key, user_id]):
        print("❌ Error: Missing NEON_DB_URL, MASTER_ENCRYPTION_KEY, or DEFAULT_USER_ID in .env")
        return False

    # Credentials to migrate
    beeminder_user = os.getenv("BEEMINDER_USERNAME")
    beeminder_token = os.getenv("BEEMINDER_AUTH_TOKEN")
    clozemaster_email = os.getenv("CLOZEMASTER_EMAIL")
    clozemaster_pass = os.getenv("CLOZEMASTER_PASSWORD")

    if not all([beeminder_user, beeminder_token, clozemaster_email, clozemaster_pass]):
        print("❌ Error: One or more credentials missing from .env (BEEMINDER_USERNAME, BEEMINDER_AUTH_TOKEN, CLOZEMASTER_EMAIL, CLOZEMASTER_PASSWORD)")
        return False

    encryption = EncryptionService(master_key)
    
    try:
        print(f"🔐 Encrypting credentials for user {user_id}...")
        enc_beeminder_token = encryption.encrypt(beeminder_token)
        enc_clozemaster_email = encryption.encrypt(clozemaster_email)
        enc_clozemaster_pass = encryption.encrypt(clozemaster_pass)
        
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                # 1. Ensure user exists with encrypted credentials (one-shot)
                cur.execute("""
                    INSERT INTO users (
                        pocket_id_sub, 
                        familiar_id, 
                        beeminder_user, 
                        beeminder_token_encrypted, 
                        clozemaster_email_encrypted, 
                        clozemaster_password_encrypted
                    ) VALUES (%s, 'yebyen', %s, %s, %s, %s)
                    ON CONFLICT (pocket_id_sub) DO UPDATE SET
                        beeminder_user = EXCLUDED.beeminder_user,
                        beeminder_token_encrypted = EXCLUDED.beeminder_token_encrypted,
                        clozemaster_email_encrypted = EXCLUDED.clozemaster_email_encrypted,
                        clozemaster_password_encrypted = EXCLUDED.clozemaster_password_encrypted,
                        familiar_id = 'yebyen'
                """, (user_id, beeminder_user, enc_beeminder_token, enc_clozemaster_email, enc_clozemaster_pass))
                
                print(f"✅ Successfully migrated and encrypted credentials for {beeminder_user} ({user_id})")
                    
            conn.commit()
        return True
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
