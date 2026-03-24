import os
import pytest
import psycopg2
import binascii
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

# Load environment variables from .env file explicitly
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Set a dummy key for the test if not present (32 bytes = 64 hex chars)
os.environ.setdefault("MASTER_ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")

def test_encrypted_credential_storage_and_retrieval():
    """
    TDG RED: Verify that we can securely store and retrieve encrypted 
    Clozemaster credentials in the Neon database on a per-user basis.
    This simulates the Rust scraper's new behavior.
    """
    db_url = os.getenv("NEON_DB_URL")
    master_key_hex = os.getenv("MASTER_ENCRYPTION_KEY")
    
    # 1. Setup mock user and credentials
    test_user_id = "test-user-credentials-123"
    test_email = "test@example.com"
    test_password = "supersecretpassword123!"
    
    # 2. Encrypt the credentials (simulating the ingestion process)
    key = binascii.unhexlify(master_key_hex)
    aesgcm = AESGCM(key)
    
    email_nonce = os.urandom(12)
    email_ciphertext = aesgcm.encrypt(email_nonce, test_email.encode(), None)
    email_encrypted_hex = binascii.hexlify(email_nonce + email_ciphertext).decode()
    
    password_nonce = os.urandom(12)
    password_ciphertext = aesgcm.encrypt(password_nonce, test_password.encode(), None)
    password_encrypted_hex = binascii.hexlify(password_nonce + password_ciphertext).decode()
    
    # 3. Store in Neon database
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Ensure the columns exist (simulating the migration)
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS clozemaster_email_encrypted TEXT;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS clozemaster_password_encrypted TEXT;")
            
            # Upsert the test user
            cur.execute("""
                INSERT INTO users (pocket_id_sub, beeminder_token_encrypted, clozemaster_email_encrypted, clozemaster_password_encrypted)
                VALUES (%s, 'dummy_token', %s, %s)
                ON CONFLICT (pocket_id_sub) DO UPDATE SET
                    clozemaster_email_encrypted = EXCLUDED.clozemaster_email_encrypted,
                    clozemaster_password_encrypted = EXCLUDED.clozemaster_password_encrypted;
            """, (test_user_id, email_encrypted_hex, password_encrypted_hex))
            conn.commit()

            # 4. Retrieve and verify decryption (simulating the Rust scraper's fetch)
            cur.execute("""
                SELECT clozemaster_email_encrypted, clozemaster_password_encrypted 
                FROM users 
                WHERE pocket_id_sub = %s;
            """, (test_user_id,))
            
            row = cur.fetchone()
            assert row is not None, "Failed to retrieve user from database"
            
            retrieved_email_hex, retrieved_password_hex = row
            assert retrieved_email_hex == email_encrypted_hex
            assert retrieved_password_hex == password_encrypted_hex
            
            # Decrypt email
            email_bytes = binascii.unhexlify(retrieved_email_hex)
            decrypted_email = aesgcm.decrypt(email_bytes[:12], email_bytes[12:], None).decode()
            
            # Decrypt password
            password_bytes = binascii.unhexlify(retrieved_password_hex)
            decrypted_password = aesgcm.decrypt(password_bytes[:12], password_bytes[12:], None).decode()
            
            # Verify they match the original plaintext
            assert decrypted_email == test_email, "Email decryption failed to match original plaintext"
            assert decrypted_password == test_password, "Password decryption failed to match original plaintext"
            
            # 5. Cleanup
            cur.execute("DELETE FROM users WHERE pocket_id_sub = %s;", (test_user_id,))
            conn.commit()
