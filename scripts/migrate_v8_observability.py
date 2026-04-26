"""
Migration v8: Observability Mandate — add last_status, last_error, intent columns
to the scheduler_election table.

Implements requirement 1 of kingdonb/mecris#245 (Epic: Observability Mandate).
Plan: yebyen/mecris#282

Idempotent: uses ADD COLUMN IF NOT EXISTS.
"""
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
        print("Adding last_status to scheduler_election...")
        cur.execute("""
            ALTER TABLE scheduler_election
            ADD COLUMN IF NOT EXISTS last_status VARCHAR(255);
        """)

        print("Adding last_error to scheduler_election...")
        cur.execute("""
            ALTER TABLE scheduler_election
            ADD COLUMN IF NOT EXISTS last_error TEXT;
        """)

        print("Adding intent to scheduler_election...")
        cur.execute("""
            ALTER TABLE scheduler_election
            ADD COLUMN IF NOT EXISTS intent VARCHAR(255);
        """)

        conn.commit()
        print("Migration v8 completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    migrate()
