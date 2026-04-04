import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("NEON_DB_URL")
try:
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), type FROM message_log GROUP BY type")
            rows = cur.fetchall()
            print("Message counts by type:")
            for r in rows:
                print(f"  {r[1]}: {r[0]}")
            cur.execute("SELECT * FROM message_log ORDER BY sent_at DESC LIMIT 5")
            print("Recent 5:")
            for r in cur.fetchall():
                print(f"  {r}")
except Exception as e:
    print(f"DB Error: {e}")
