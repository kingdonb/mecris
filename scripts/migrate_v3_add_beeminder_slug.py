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
        print("Adding beeminder_slug to language_stats...")
        cur.execute("ALTER TABLE language_stats ADD COLUMN IF NOT EXISTS beeminder_slug VARCHAR(255);")
        
        # Populate existing known mappings
        known_mappings = {
            "ARABIC": "reviewstack",
            "GREEK": "ellinika"
        }
        
        for lang, slug in known_mappings.items():
            print(f"Setting beeminder_slug={slug} for {lang}...")
            cur.execute("UPDATE language_stats SET beeminder_slug = %s WHERE language_name = %s;", (slug, lang))

        conn.commit()
        print("Migration v3 completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
