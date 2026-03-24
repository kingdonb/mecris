import os
import binascii
import psycopg2
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

load_dotenv()

def encrypt(plaintext, key_hex):
    key = binascii.unhexlify(key_hex)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return binascii.hexlify(nonce + ciphertext).decode()

key = os.getenv("MASTER_ENCRYPTION_KEY")
db_url = os.getenv("NEON_DB_URL")

if not all([key, db_url]):
    print("❌ Error: Missing MASTER_ENCRYPTION_KEY or NEON_DB_URL in .env")
    exit(1)

with psycopg2.connect(db_url) as conn:
    with conn.cursor() as cur:
        # 1. Fetch the plaintext token
        cur.execute("SELECT beeminder_token_encrypted FROM users WHERE pocket_id_sub = 'c0a81a4b-115a-4eb6-bc2c-40908c58bf64'")
        row = cur.fetchone()
        if not row:
            print("❌ User not found.")
            exit(1)
        token = row[0]

        # Check if it's already encrypted
        if len(token) > 40:
             print("⚠️ Token already looks encrypted. Skipping.")
             exit(0)

        # 2. Encrypt it
        token_enc = encrypt(token, key)

        # 3. Update the DB
        cur.execute("""
            UPDATE users
            SET beeminder_token_encrypted = %s
            WHERE pocket_id_sub = 'c0a81a4b-115a-4eb6-bc2c-40908c58bf64'
        """, (token_enc,))
        conn.commit()
        print(f"✅ Beeminder token encrypted and updated in DB!")
