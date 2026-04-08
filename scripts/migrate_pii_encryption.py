import os
import psycopg2
import logging
from dotenv import load_dotenv
from services.encryption_service import EncryptionService

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mecris.migration")

def migrate():
    neon_url = os.getenv("NEON_DB_URL")
    master_key = os.getenv("MASTER_ENCRYPTION_KEY")
    
    if not neon_url:
        logger.error("NEON_DB_URL not set")
        return False
    
    if not master_key:
        logger.error("MASTER_ENCRYPTION_KEY not set")
        return False

    encryption = EncryptionService(master_key)

    try:
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                # 1. Check and add columns to 'users'
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
                user_columns = [row[0] for row in cur.fetchall()]
                
                cols_to_add = {
                    'beeminder_user_encrypted': 'TEXT',
                    'phone_number_encrypted': 'TEXT',
                    'clozemaster_email_encrypted': 'TEXT',
                    'clozemaster_password_encrypted': 'TEXT'
                }
                
                for col, col_type in cols_to_add.items():
                    if col not in user_columns:
                        logger.info(f"Adding column {col} to users table...")
                        cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                
                # 2. Check and add columns to 'message_log'
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'message_log'")
                log_columns = [row[0] for row in cur.fetchall()]
                
                if 'status' not in log_columns:
                    logger.info("Adding column status to message_log table...")
                    cur.execute("ALTER TABLE message_log ADD COLUMN status VARCHAR(50)")
                if 'error_msg' not in log_columns:
                    logger.info("Adding column error_msg to message_log table...")
                    cur.execute("ALTER TABLE message_log ADD COLUMN error_msg TEXT")
                if 'content' not in log_columns:
                    logger.info("Adding column content to message_log table...")
                    cur.execute("ALTER TABLE message_log ADD COLUMN content TEXT")

                # 3. Migrate data for beeminder_user if beeminder_user_encrypted is empty
                logger.info("Checking for data to migrate in users table...")
                cur.execute("SELECT pocket_id_sub, beeminder_user FROM users WHERE beeminder_user_encrypted IS NULL AND beeminder_user IS NOT NULL")
                rows = cur.fetchall()
                for user_id, plaintext_user in rows:
                    if plaintext_user:
                        logger.info(f"Encrypting beeminder_user for {user_id}...")
                        encrypted = encryption.encrypt(plaintext_user)
                        cur.execute("UPDATE users SET beeminder_user_encrypted = %s WHERE pocket_id_sub = %s", (encrypted, user_id))

                # 4. (Optional) Check clozemaster creds from .env if missing in DB
                # This handles the case where they are in .env but not yet in DB
                beeminder_token = os.getenv("BEEMINDER_AUTH_TOKEN")
                clozemaster_email = os.getenv("CLOZEMASTER_EMAIL")
                clozemaster_pass = os.getenv("CLOZEMASTER_PASSWORD")
                default_user_id = os.getenv("DEFAULT_USER_ID")

                if default_user_id:
                    cur.execute("SELECT beeminder_token_encrypted, clozemaster_email_encrypted FROM users WHERE pocket_id_sub = %s", (default_user_id,))
                    row = cur.fetchone()
                    if row:
                        db_token, db_email = row
                        updates = []
                        params = []
                        if not db_token and beeminder_token:
                            logger.info(f"Migrating BEEMINDER_AUTH_TOKEN from .env for {default_user_id}")
                            updates.append("beeminder_token_encrypted = %s")
                            params.append(encryption.encrypt(beeminder_token))
                        if not db_email and clozemaster_email:
                            logger.info(f"Migrating CLOZEMASTER_EMAIL from .env for {default_user_id}")
                            updates.append("clozemaster_email_encrypted = %s")
                            params.append(encryption.encrypt(clozemaster_email))
                        if clozemaster_pass and not row[1]: # clozemaster_password_encrypted
                            updates.append("clozemaster_password_encrypted = %s")
                            params.append(encryption.encrypt(clozemaster_pass))
                        
                        if updates:
                            params.append(default_user_id)
                            cur.execute(f"UPDATE users SET {', '.join(updates)} WHERE pocket_id_sub = %s", tuple(params))

                conn.commit()
                logger.info("Migration successful.")
                return True
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    migrate()
