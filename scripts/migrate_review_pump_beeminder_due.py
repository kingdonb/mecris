import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def migrate():
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        print("Error: NEON_DB_URL not found")
        return

    conn = psycopg2.connect(neon_url)
    cur = conn.cursor()

    try:
        print("Adding beeminder_road_today / beeminder_due_today to language_stats...")
        cur.execute("ALTER TABLE language_stats ADD COLUMN IF NOT EXISTS beeminder_road_today INTEGER;")
        cur.execute("ALTER TABLE language_stats ADD COLUMN IF NOT EXISTS beeminder_due_today INTEGER NOT NULL DEFAULT 0;")

        conn.commit()
        print("Migration review_pump_beeminder_due completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
