import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("NEON_DB_URL")
try:
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'message_log';
            """)
            for r in cur.fetchall():
                print(f"  {r[0]}: {r[1]}")
except Exception as e:
    print(f"DB Error: {e}")
