import os
import psycopg2
from dotenv import load_dotenv
from services.encryption_service import EncryptionService

load_dotenv()

def sync_beeminder_to_cloud():
    db_url = os.getenv("NEON_DB_URL")
    beeminder_token = os.getenv("BEEMINDER_AUTH_TOKEN")
    beeminder_user = os.getenv("BEEMINDER_USERNAME", "yebyenw")
    user_sub = os.getenv("DEFAULT_USER_ID", "c0a81a4b-115a-4eb6-bc2c-40908c58bf64")
    
    if not db_url or not beeminder_token:
        print("❌ Error: Missing configuration in .env")
        return

    encryption = EncryptionService()
    try:
        print(f"⏳ Connecting to Neon...")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        print(f"🔐 Encrypting credentials for user {user_sub}...")
        enc_token = encryption.encrypt(beeminder_token)
        enc_user = encryption.encrypt(beeminder_user)

        print(f"🔄 Syncing Beeminder credentials to cloud...")
        query = """
            UPDATE users 
            SET beeminder_token_encrypted = %s, 
                beeminder_user_encrypted = %s,
                beeminder_user = %s,
                beeminder_goal = 'bike'
            WHERE pocket_id_sub = %s
        """
        cur.execute(query, (enc_token, enc_user, beeminder_user, user_sub))
        
        if cur.rowcount == 0:
            print("⚠️ Warning: User not found in database. Attempting insert...")
            insert_query = """
                INSERT INTO users (pocket_id_sub, beeminder_token_encrypted, beeminder_user_encrypted, beeminder_user, beeminder_goal)
                VALUES (%s, %s, %s, %s, 'bike')
            """
            cur.execute(insert_query, (user_sub, enc_token, enc_user, beeminder_user))
        
        conn.commit()
        print("✅ Beeminder Cloud Sync complete!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    sync_beeminder_to_cloud()
