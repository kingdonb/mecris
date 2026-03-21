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

    tables_to_migrate = [
        "scheduler_election",
        "usage_sessions",
        "goals",
        "groq_odometer_readings",
        "groq_monthly_summaries",
        "groq_reminders",
        "alert_log",
        "message_log",
        "budget_allocations",
        "provider_usage",
        "reconciliation_jobs",
        "provider_cache",
        "apscheduler_jobs"
    ]

    try:
        cur.execute("SELECT pocket_id_sub FROM users LIMIT 1;")
        default_user = cur.fetchone()
        if not default_user:
            print("Error: No user found in 'users' table to set as default.")
            return
        default_user_id = default_user[0]
        print(f"Using default user_id: {default_user_id}")

        for table in tables_to_migrate:
            print(f"Migrating table: {table}...")
            
            # 1. Add user_id column
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id VARCHAR(255) REFERENCES users(pocket_id_sub);")
            
            # 2. Update existing rows
            cur.execute(f"UPDATE {table} SET user_id = %s WHERE user_id IS NULL;", (default_user_id,))
            
            # 3. Handle specific table constraints
            if table == "scheduler_election":
                print(f"Updating constraints for {table}...")
                cur.execute("ALTER TABLE scheduler_election DROP CONSTRAINT IF EXISTS scheduler_election_role_key;")
                cur.execute("ALTER TABLE scheduler_election ADD CONSTRAINT scheduler_election_user_role_key UNIQUE (user_id, role);")
            
            if table == "goals":
                # Assuming id is PK, but user_id + slug might be better if slug exists
                # For now just add user_id as a filterable column
                pass

        conn.commit()
        print("Migration v4 completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
