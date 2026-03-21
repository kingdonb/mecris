import os
import psycopg2
from psycopg2.extras import RealDictCursor

neon_url = os.getenv("NEON_DB_URL")
if not neon_url:
    print("NEON_DB_URL not set")
    exit(1)

try:
    with psycopg2.connect(neon_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check current max id
            cur.execute("SELECT MAX(id) FROM groq_odometer_readings")
            max_id = cur.fetchone()['max']
            print(f"Current MAX(id): {max_id}")
            
            # Check current sequence value
            cur.execute("SELECT last_value FROM groq_odometer_readings_id_seq")
            last_val = cur.fetchone()['last_value']
            print(f"Current sequence last_value: {last_val}")
            
            if max_id and max_id >= last_val:
                print(f"Resetting sequence to {max_id + 1}")
                cur.execute(f"SELECT setval('groq_odometer_readings_id_seq', {max_id})")
                print("Sequence reset successfully")
            else:
                print("Sequence seems fine or table is empty")
except Exception as e:
    print(f"Error: {e}")
