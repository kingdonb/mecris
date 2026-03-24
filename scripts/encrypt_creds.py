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
email = os.getenv("CLOZEMASTER_EMAIL")
password = os.getenv("CLOZEMASTER_PASSWORD")
db_url = os.getenv("NEON_DB_URL")

if not all([key, email, password, db_url]):
    print("❌ Error: Missing required environment variables in .env")
    exit(1)

email_enc = encrypt(email, key)
pass_enc = encrypt(password, key)

with psycopg2.connect(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE users
            SET clozemaster_email_encrypted = %s,
                clozemaster_password_encrypted = %s
            WHERE pocket_id_sub = 'c0a81a4b-115a-4eb6-bc2c-40908c58bf64'
        """, (email_enc, pass_enc))
        conn.commit()
        print("✅ Database updated with credentials encrypted using the NEW V2 key!")
