import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("NEON_DB_URL")
try:
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE message_log ADD COLUMN IF NOT EXISTS status text DEFAULT 'sent';")
            cur.execute("ALTER TABLE message_log ADD COLUMN IF NOT EXISTS error_msg text;")
            conn.commit()
            print("Successfully updated message_log schema.")
except Exception as e:
    print(f"DB Error: {e}")
