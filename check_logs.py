import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("NEON_DB_URL")
if not db_url:
    print("No NEON_DB_URL")
    exit(1)

try:
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT sent_at, type, user_id FROM message_log ORDER BY sent_at DESC LIMIT 20")
            rows = cur.fetchall()
            print("Recent message_log entries:")
            for r in rows:
                print(f"  {r[0]} | {r[1]} | {r[2]}")
except Exception as e:
    print(f"DB Error: {e}")
