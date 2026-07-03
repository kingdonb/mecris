import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def seed_test_database():
    db_url = os.getenv("NEON_DB_URL")
    if not db_url:
        print("❌ Error: NEON_DB_URL not found in environment.")
        return

    user_id = "c0a81a4b-115a-4eb6-bc2c-40908c58bf64"
    
    try:
        print(f"⏳ Connecting to database to seed test data...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Insert user if not exists
        print(f"👤 Seeding user {user_id}...")
        cur.execute("""
            INSERT INTO users (pocket_id_sub, familiar_id, beeminder_goal, phone_verified)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (pocket_id_sub) DO UPDATE 
            SET familiar_id = EXCLUDED.familiar_id, beeminder_goal = EXCLUDED.beeminder_goal;
        """, (user_id, "yebyen", "bike", True))

        # Insert language stats for Arabic
        print("📚 Seeding ARABIC language stats...")
        cur.execute("""
            INSERT INTO language_stats (
                user_id, language_name, current_reviews, tomorrow_reviews, 
                next_7_days_reviews, daily_rate, safebuf, derail_risk, 
                pump_multiplier, beeminder_slug, daily_completions
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, language_name) DO UPDATE 
            SET current_reviews = EXCLUDED.current_reviews,
                tomorrow_reviews = EXCLUDED.tomorrow_reviews,
                next_7_days_reviews = EXCLUDED.next_7_days_reviews,
                daily_rate = EXCLUDED.daily_rate,
                safebuf = EXCLUDED.safebuf,
                derail_risk = EXCLUDED.derail_risk,
                beeminder_slug = EXCLUDED.beeminder_slug,
                daily_completions = EXCLUDED.daily_completions;
        """, (user_id, "ARABIC", 10, 20, 50, 5.0, 3, "CAUTION", 1.0, "reviewstack", 5))

        # Insert language stats for Greek
        print("📚 Seeding GREEK language stats...")
        cur.execute("""
            INSERT INTO language_stats (
                user_id, language_name, current_reviews, tomorrow_reviews, 
                next_7_days_reviews, daily_rate, safebuf, derail_risk, 
                pump_multiplier, beeminder_slug, daily_completions
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, language_name) DO UPDATE 
            SET current_reviews = EXCLUDED.current_reviews,
                tomorrow_reviews = EXCLUDED.tomorrow_reviews,
                next_7_days_reviews = EXCLUDED.next_7_days_reviews,
                daily_rate = EXCLUDED.daily_rate,
                safebuf = EXCLUDED.safebuf,
                derail_risk = EXCLUDED.derail_risk,
                beeminder_slug = EXCLUDED.beeminder_slug,
                daily_completions = EXCLUDED.daily_completions;
        """, (user_id, "GREEK", 5, 10, 30, 2.0, 19, "SAFE", 1.0, "ellinika", 10))

        conn.commit()
        print("✅ Test database seeding complete!")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error seeding database: {e}")

if __name__ == "__main__":
    seed_test_database()
