#!/usr/bin/env python3
"""
Migration script to create the budget_governor_spend_log table in Neon.

Run with: python scripts/migrate_budget_governor_spend_log.py
"""
import os
import psycopg2
from dotenv import load_dotenv

# Load environment
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

NEON_DB_URL = os.getenv("NEON_DB_URL")

if not NEON_DB_URL:
    print("ERROR: NEON_DB_URL not set in environment")
    exit(1)

SQL = """
-- Budget Governor Spend Log table for 5%/5% envelope tracking
CREATE TABLE IF NOT EXISTS budget_governor_spend_log (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    bucket TEXT NOT NULL,
    cost NUMERIC(10, 6) NOT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model TEXT,
    request_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for 39-minute rolling window queries (bucket + timestamp)
CREATE INDEX IF NOT EXISTS idx_budget_governor_spend_log_bucket_ts
    ON budget_governor_spend_log (bucket, ts);

-- Optional: index for user-scoped queries
CREATE INDEX IF NOT EXISTS idx_budget_governor_spend_log_user_ts
    ON budget_governor_spend_log (user_id, ts);
"""

def main():
    print("Creating budget_governor_spend_log table...")
    try:
        with psycopg2.connect(NEON_DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(SQL)
                print("✅ Table created successfully")
                
                # Verify
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'budget_governor_spend_log'
                    ORDER BY ordinal_position;
                """)
                print("\nTable schema:")
                for row in cur.fetchall():
                    print(f"  {row[0]}: {row[1]} (nullable: {row[2]})")
                
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = 'budget_governor_spend_log';
                """)
                print("\nIndexes:")
                for row in cur.fetchall():
                    print(f"  {row[0]}: {row[1]}")
                    
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()