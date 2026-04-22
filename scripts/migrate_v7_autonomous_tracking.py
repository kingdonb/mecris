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
        print("Creating token_bank table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS token_bank (
                user_id VARCHAR(255) PRIMARY KEY REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
                daily_allowance INTEGER NOT NULL DEFAULT 50000,
                tokens_used_today INTEGER NOT NULL DEFAULT 0,
                last_reset_date DATE NOT NULL DEFAULT CURRENT_DATE
            );
        """)

        print("Creating autonomous_turns table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS autonomous_turns (
                turn_id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
                agent_role VARCHAR(64) NOT NULL,
                start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                end_time TIMESTAMPTZ,
                exit_code INTEGER,
                tokens_consumed INTEGER NOT NULL DEFAULT 0,
                summary TEXT
            );
        """)

        conn.commit()
        print("Migration v7 completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    migrate()
