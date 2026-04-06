import os
import psycopg2
from services.encryption_service import EncryptionService
from datetime import datetime

def verify():
    neon_url = os.getenv("NEON_DB_URL")
    enc = EncryptionService()
    
    if not enc.aesgcm:
        print("Encryption not active (MASTER_ENCRYPTION_KEY missing)")
        return

    test_msg = "Sunkworks secret message"
    ciphertext = enc.encrypt(test_msg)
    
    print(f"Original: {test_msg}")
    print(f"Ciphertext: {ciphertext}")
    
    with psycopg2.connect(neon_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO message_log (date, type, sent_at, user_id, status, content) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (datetime.now().date(), "encryption_test", datetime.now(), "c0a81a4b-115a-4eb6-bc2c-40908c58bf64", "sent", ciphertext)
            )
            row_id = cur.fetchone()[0]
            print(f"Inserted row {row_id}")
            
            cur.execute("SELECT content FROM message_log WHERE id = %s", (row_id,))
            db_val = cur.fetchone()[0]
            print(f"Stored value: {db_val}")
            
            if db_val == test_msg:
                print("FAILURE: Stored as plaintext!")
            elif db_val == ciphertext:
                print("SUCCESS: Stored as ciphertext.")
                
                decrypted = enc.decrypt(db_val)
                print(f"Decrypted: {decrypted}")
                if decrypted == test_msg:
                    print("SUCCESS: Decryption roundtrip works.")
            else:
                print(f"ERROR: Stored value mismatch: {db_val}")

if __name__ == "__main__":
    verify()
