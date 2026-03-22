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
        print("Adding total_points and last_points to language_stats...")
        cur.execute("ALTER TABLE language_stats ADD COLUMN IF NOT EXISTS total_points INTEGER DEFAULT 0;")
        cur.execute("ALTER TABLE language_stats ADD COLUMN IF NOT EXISTS last_points INTEGER DEFAULT 0;")
        
        conn.commit()
        print("Migration v5 completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
