import os
import psycopg2
from datetime import datetime

neon_url = os.getenv("NEON_DB_URL")
if not neon_url:
    print("NEON_DB_URL not set")
    exit(1)

try:
    with psycopg2.connect(neon_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT role, process_id, heartbeat, heartbeat > NOW() - INTERVAL '90 seconds' as is_active FROM scheduler_election;")
            rows = cur.fetchall()
            print("role | process_id | heartbeat | is_active")
            print("-" * 50)
            for row in rows:
                print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]}")
            
            cur.execute("SELECT NOW();")
            print(f"\nDB NOW(): {cur.fetchone()[0]}")
            print(f"Local NOW (naive): {datetime.now()}")
            print(f"Local NOW (UTC): {datetime.utcnow()}")
except Exception as e:
    print(f"Error: {e}")
