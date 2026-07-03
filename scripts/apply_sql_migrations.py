import os
import glob
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def apply_sql_migrations():
    db_url = os.getenv("NEON_DB_URL")
    if not db_url:
        print("❌ Error: NEON_DB_URL not found in environment.")
        return

    migrations_dir = "scripts/migrations"
    if not os.path.exists(migrations_dir):
        print(f"❌ Error: Migrations directory {migrations_dir} not found.")
        return

    # Find all SQL files in scripts/migrations/ sorted alphabetically
    sql_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
    if not sql_files:
        print("ℹ️ No SQL migrations found in scripts/migrations/.")
        return

    try:
        print(f"⏳ Connecting to database to apply SQL migrations...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        for sql_file in sql_files:
            print(f"📖 Reading migration {os.path.basename(sql_file)}...")
            with open(sql_file, "r") as f:
                sql_content = f.read()

            print(f"🚀 Executing {os.path.basename(sql_file)}...")
            # We execute each file's content
            cur.execute(sql_content)
            conn.commit()
            print(f"✅ Applied {os.path.basename(sql_file)} successfully!")

        cur.close()
        conn.close()
        print("🎉 All SQL migrations applied successfully!")
    except Exception as e:
        print(f"❌ Database error applying migrations: {e}")
        raise e

if __name__ == "__main__":
    apply_sql_migrations()
