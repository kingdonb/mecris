import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
neon_url = os.getenv("NEON_DB_URL")
if neon_url:
    try:
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE language_stats
                    ADD COLUMN IF NOT EXISTS safebuf INTEGER DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS derail_risk VARCHAR(50) DEFAULT 'SAFE';
                """)
                conn.commit()
                print("Schema updated successfully.")
    except Exception as e:
        print(f"Error: {e}")
