import os
import sqlite3
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def migrate():
    sqlite_db = "mecris_virtual_budget.db"
    neon_url = os.getenv("NEON_DB_URL")
    
    if not neon_url:
        print("Error: NEON_DB_URL not found in environment")
        return

    print(f"Connecting to SQLite: {sqlite_db}")
    sqlite_conn = sqlite3.connect(sqlite_db)
    sqlite_cur = sqlite_conn.cursor()

    print(f"Connecting to Neon PostgreSQL...")
    neon_conn = psycopg2.connect(neon_url)
    neon_cur = neon_conn.cursor()

    # Define Schema for Virtual Budget
    schema_queries = [
        """
        CREATE TABLE IF NOT EXISTS budget_allocations (
            id SERIAL PRIMARY KEY,
            period_type TEXT NOT NULL,
            budget_amount DOUBLE PRECISION NOT NULL,
            remaining_amount DOUBLE PRECISION NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS provider_usage (
            id SERIAL PRIMARY KEY,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            estimated_cost DOUBLE PRECISION NOT NULL,
            actual_cost DOUBLE PRECISION DEFAULT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
            session_type TEXT DEFAULT 'interactive',
            notes TEXT DEFAULT '',
            reconciled BOOLEAN DEFAULT FALSE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS reconciliation_jobs (
            id SERIAL PRIMARY KEY,
            provider TEXT NOT NULL,
            job_date DATE NOT NULL,
            estimated_total DOUBLE PRECISION NOT NULL,
            actual_total DOUBLE PRECISION NOT NULL,
            drift_percentage DOUBLE PRECISION NOT NULL,
            records_reconciled INTEGER NOT NULL,
            reconciled_at TIMESTAMPTZ NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS provider_cache (
            id SERIAL PRIMARY KEY,
            provider TEXT NOT NULL,
            cache_key TEXT NOT NULL,
            cache_data TEXT NOT NULL,
            cached_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            UNIQUE(provider, cache_key)
        );
        """
    ]

    print("Creating virtual budget schema in Neon...")
    for q in schema_queries:
        neon_cur.execute(q)
    neon_conn.commit()

    # Tables to migrate
    tables = [
        ("budget_allocations", ["id", "period_type", "budget_amount", "remaining_amount", "period_start", "period_end", "created_at", "updated_at"]),
        ("provider_usage", ["id", "provider", "model", "input_tokens", "output_tokens", "estimated_cost", "actual_cost", "timestamp", "session_type", "notes", "reconciled"]),
        ("reconciliation_jobs", ["id", "provider", "job_date", "estimated_total", "actual_total", "drift_percentage", "records_reconciled", "reconciled_at"]),
        ("provider_cache", ["id", "provider", "cache_key", "cache_data", "cached_at", "expires_at"])
    ]

    for table_name, columns in tables:
        print(f"Migrating table: {table_name}...")
        
        # Get data from SQLite
        try:
            sqlite_cur.execute(f"SELECT {', '.join(columns)} FROM {table_name}")
            rows = sqlite_cur.fetchall()
        except sqlite3.OperationalError as e:
            print(f"  Table {table_name} skipped (likely empty or missing): {e}")
            continue
        
        if not rows:
            print(f"  No data found for {table_name}")
            continue

        # Prepare insertion query
        col_str = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        
        conflict_clause = ""
        if table_name == "provider_cache":
            conflict_clause = "ON CONFLICT (provider, cache_key) DO UPDATE SET " + ", ".join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ["id", "provider", "cache_key"]])
        else:
            conflict_clause = "ON CONFLICT (id) DO UPDATE SET " + ", ".join([f"{col} = EXCLUDED.{col}" for col in columns if col != "id"])
        
        upsert_query = f"""
            INSERT INTO {table_name} ({col_str})
            VALUES ({placeholders})
            {conflict_clause}
        """

        for row in rows:
            neon_cur.execute(upsert_query, row)
        print(f"  Migrated {len(rows)} rows to {table_name}")

    neon_conn.commit()
    print("Virtual budget migration completed successfully!")

    sqlite_conn.close()
    neon_conn.close()

if __name__ == "__main__":
    migrate()
