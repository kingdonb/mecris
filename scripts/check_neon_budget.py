import os
import psycopg2
from psycopg2.extras import RealDictCursor

neon_url = os.getenv("NEON_DB_URL")
user_id = os.getenv("DEFAULT_USER_ID", "yebyen")

if not neon_url:
    print("NEON_DB_URL not set")
    exit(1)

try:
    with psycopg2.connect(neon_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            print(f"Checking budget for {user_id}...")
            cur.execute("SELECT * FROM budget_tracking WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                print(f"Found budget: {row}")
            else:
                print("No budget found.")
                
            print("\nChecking all users in budget_tracking:")
            cur.execute("SELECT user_id FROM budget_tracking")
            users = cur.fetchall()
            print(f"Users: {[u['user_id'] for u in users]}")
            
            print("\nChecking users table:")
            cur.execute("SELECT pocket_id_sub, email FROM users")
            all_users = cur.fetchall()
            for u in all_users:
                print(f"User: {u['pocket_id_sub']} ({u['email']})")

except Exception as e:
    print(f"Error: {e}")
