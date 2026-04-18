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
        print("Adding phone_verified to users table...")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE;")

        print("Adding vacation_mode_until to users table...")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS vacation_mode_until TIMESTAMPTZ;")

        print("Adding user_id to scheduler_election and fixing unique constraint...")
        # Add user_id column if not present (existing rows will be NULL — acceptable for migration)
        cur.execute("ALTER TABLE scheduler_election ADD COLUMN IF NOT EXISTS user_id VARCHAR(255) REFERENCES users(pocket_id_sub) ON DELETE CASCADE;")
        # Drop the old single-column unique constraint if it exists
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'scheduler_election_role_key'
                      AND conrelid = 'scheduler_election'::regclass
                ) THEN
                    ALTER TABLE scheduler_election DROP CONSTRAINT scheduler_election_role_key;
                END IF;
            END $$;
        """)
        # Add composite unique constraint (user_id, role) if not present
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'scheduler_election_user_id_role_key'
                      AND conrelid = 'scheduler_election'::regclass
                ) THEN
                    ALTER TABLE scheduler_election ADD CONSTRAINT scheduler_election_user_id_role_key UNIQUE (user_id, role);
                END IF;
            END $$;
        """)

        print("Creating phone_verifications table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS phone_verifications (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
                code_hash TEXT NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                attempts INTEGER DEFAULT 0,
                UNIQUE (user_id)
            );
        """)

        conn.commit()
        print("Migration v6 completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
