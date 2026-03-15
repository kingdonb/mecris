import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def migrate():
    sqlite_db = "mecris_usage.db"
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

    # Define Schema
    schema_queries = [
        """
        CREATE TABLE IF NOT EXISTS usage_sessions (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            estimated_cost DOUBLE PRECISION NOT NULL,
            session_type TEXT NOT NULL,
            notes TEXT DEFAULT ''
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS budget_tracking (
            id INTEGER PRIMARY KEY,
            total_budget DOUBLE PRECISION NOT NULL,
            remaining_budget DOUBLE PRECISION NOT NULL,
            budget_period_start TEXT NOT NULL,
            budget_period_end TEXT NOT NULL,
            last_updated TIMESTAMPTZ NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS goals (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ DEFAULT NULL,
            due_date TEXT DEFAULT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS alert_log (
            id SERIAL PRIMARY KEY,
            alert_type TEXT NOT NULL,
            alert_level TEXT NOT NULL,
            message TEXT NOT NULL,
            sent_at TIMESTAMPTZ NOT NULL,
            context TEXT DEFAULT ''
        );
        """
    ]

    print("Creating schema in Neon...")
    for q in schema_queries:
        neon_cur.execute(q)
    neon_conn.commit()

    # Tables to migrate
    tables = [
        ("usage_sessions", ["id", "timestamp", "model", "input_tokens", "output_tokens", "estimated_cost", "session_type", "notes"]),
        ("budget_tracking", ["id", "total_budget", "remaining_budget", "budget_period_start", "budget_period_end", "last_updated"]),
        ("goals", ["id", "title", "description", "priority", "status", "created_at", "completed_at", "due_date"]),
        ("alert_log", ["id", "alert_type", "alert_level", "message", "sent_at", "context"])
    ]

    for table_name, columns in tables:
        print(f"Migrating table: {table_name}...")
        
        # Get data from SQLite
        sqlite_cur.execute(f"SELECT {', '.join(columns)} FROM {table_name}")
        rows = sqlite_cur.fetchall()
        
        if not rows:
            print(f"  No data found for {table_name}")
            continue

        # Prepare insertion query
        col_str = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        
        # We use ON CONFLICT (id) DO UPDATE for tables with ID
        conflict_col = "id"
        update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns if col != conflict_col])
        
        upsert_query = f"""
            INSERT INTO {table_name} ({col_str})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_col}) DO UPDATE SET {update_set}
        """

        for row in rows:
            neon_cur.execute(upsert_query, row)
        print(f"  Migrated {len(rows)} rows to {table_name}")

    neon_conn.commit()
    print("Migration completed successfully!")

    sqlite_conn.close()
    neon_conn.close()

if __name__ == "__main__":
    migrate()
