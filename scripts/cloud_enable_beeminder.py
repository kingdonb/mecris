import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def sync_beeminder_to_cloud():
    db_url = os.getenv("NEON_DB_URL")
    beeminder_token = os.getenv("BEEMINDER_AUTH_TOKEN")
    user_sub = "c0a81a4b-115a-4eb6-bc2c-40908c58bf64"
    
    if not db_url or not beeminder_token:
        print("❌ Error: Missing configuration in .env")
        return

    try:
        print(f"⏳ Connecting to Neon...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        print(f"🔄 Syncing Beeminder token for user {user_sub}...")
        query = """
            UPDATE users 
            SET beeminder_token_encrypted = %s, 
                beeminder_goal = 'bike',
                beeminder_user = 'yebyenw'
            WHERE pocket_id_sub = %s
        """
        cur.execute(query, (beeminder_token, user_sub))
        
        if cur.rowcount == 0:
            print("⚠️ Warning: User not found in database. Attempting insert...")
            insert_query = """
                INSERT INTO users (pocket_id_sub, beeminder_token_encrypted, beeminder_goal, beeminder_user)
                VALUES (%s, %s, 'bike', 'yebyenw')
            """
            cur.execute(insert_query, (user_sub, beeminder_token))
        
        conn.commit()
        print("✅ Beeminder Cloud Sync complete!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    sync_beeminder_to_cloud()
