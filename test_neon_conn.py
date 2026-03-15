import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
neon_url = os.getenv("NEON_DB_URL")
print(f"Connecting to {neon_url[:20]}...")
try:
    with psycopg2.connect(neon_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            print(f"Connection successful: {cur.fetchone()}")
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
            print(f"Tables: {[r[0] for r in cur.fetchall()]}")
except Exception as e:
    print(f"Connection failed: {e}")
