import os
import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

def migrate():
    neon_url = os.getenv("NEON_DB_URL")
    default_user_id = os.getenv("DEFAULT_USER_ID")
    
    if not neon_url:
        logger.error("NEON_DB_URL not set")
        return

    try:
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                # Add familiar_id column if it doesn't exist
                cur.execute("""
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'familiar_id'
                """)
                if not cur.fetchone():
                    logger.info("Adding familiar_id column to users table...")
                    cur.execute("ALTER TABLE users ADD COLUMN familiar_id TEXT UNIQUE")
                
                # Update the default user with the familiar_id 'yebyen'
                if default_user_id:
                    logger.info(f"Setting familiar_id='yebyen' for user {default_user_id}...")
                    cur.execute("""
                        UPDATE users SET familiar_id = %s 
                        WHERE pocket_id_sub = %s OR beeminder_user = 'yebyenw'
                    """, ("yebyen", default_user_id))
                    
                conn.commit()
                logger.info("Migration successful.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
