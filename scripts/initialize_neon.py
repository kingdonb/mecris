import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def initialize_neon():
    db_url = os.getenv("NEON_DB_URL")
    if not db_url:
        print("❌ Error: NEON_DB_URL not found in .env")
        return

    schema_path = "mecris-go-spin/schema.sql"
    if not os.path.exists(schema_path):
        print(f"❌ Error: {schema_path} not found")
        return

    try:
        print(f"⏳ Connecting to Neon...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        print(f"📖 Reading {schema_path}...")
        with open(schema_path, "r") as f:
            schema_sql = f.read()

        print(f"🚀 Executing schema...")
        cur.execute(schema_sql)
        conn.commit()

        print("✅ Neon Schema initialized successfully!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    initialize_neon()
