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
        print("Adding user_id to language_stats...")
        # 1. Add user_id column
        cur.execute("ALTER TABLE language_stats ADD COLUMN IF NOT EXISTS user_id VARCHAR(255) REFERENCES users(pocket_id_sub);")
        
        # 2. Update existing rows to a default user (e.g., the first user in the users table)
        cur.execute("SELECT pocket_id_sub FROM users LIMIT 1;")
        default_user = cur.fetchone()
        if default_user:
            default_user_id = default_user[0]
            print(f"Setting default user_id to {default_user_id} for existing language_stats...")
            cur.execute("UPDATE language_stats SET user_id = %s WHERE user_id IS NULL;", (default_user_id,))
        
        # 3. Change Primary Key to (user_id, language_name)
        print("Updating language_stats primary key...")
        cur.execute("ALTER TABLE language_stats DROP CONSTRAINT IF EXISTS language_stats_pkey;")
        cur.execute("ALTER TABLE language_stats ADD PRIMARY KEY (user_id, language_name);")

        print("Adding user_id to budget_tracking...")
        # 4. Add user_id column to budget_tracking
        cur.execute("ALTER TABLE budget_tracking ADD COLUMN IF NOT EXISTS user_id VARCHAR(255) REFERENCES users(pocket_id_sub);")
        if default_user:
            print(f"Setting default user_id to {default_user_id} for existing budget_tracking...")
            cur.execute("UPDATE budget_tracking SET user_id = %s WHERE user_id IS NULL;", (default_user_id,))

        conn.commit()
        print("Migration v2 completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
