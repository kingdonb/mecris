import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()
neon_url = os.getenv("NEON_DB_URL")
if neon_url:
    conn = psycopg2.connect(neon_url)
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM message_log LIMIT 1")
        print("Neon table 'message_log' exists.")
    except Exception as e:
        print("Neon table check error:", e)
        conn.rollback()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS message_log (
                date DATE,
                type TEXT,
                sent_at TIMESTAMPTZ,
                PRIMARY KEY (date, type)
            )
        """)
        conn.commit()
        print("Created message_log table in Neon.")
