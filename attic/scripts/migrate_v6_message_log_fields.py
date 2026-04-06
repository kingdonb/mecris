import os
import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

def migrate():
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        logger.error("NEON_DB_URL not set")
        return

    try:
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                # Add columns if they don't exist
                columns_to_add = [
                    ("content", "TEXT"),
                    ("channel", "VARCHAR(50) DEFAULT 'whatsapp'")
                ]
                
                for col_name, col_type in columns_to_add:
                    try:
                        cur.execute(f"ALTER TABLE message_log ADD COLUMN {col_name} {col_type}")
                        logger.info(f"Added column {col_name} to message_log")
                    except psycopg2.errors.DuplicateColumn:
                        conn.rollback()
                        logger.info(f"Column {col_name} already exists in message_log")
                    except Exception as e:
                        conn.rollback()
                        logger.error(f"Failed to add column {col_name}: {e}")

                # Handle id column (SERIAL PRIMARY KEY)
                try:
                    # First check for existing primary key and drop it
                    cur.execute("""
                        SELECT conname 
                        FROM pg_constraint 
                        WHERE conrelid = 'message_log'::regclass AND contype = 'p'
                    """)
                    row = cur.fetchone()
                    if row:
                        pk_name = row[0]
                        cur.execute(f"ALTER TABLE message_log DROP CONSTRAINT {pk_name}")
                        logger.info(f"Dropped old primary key constraint {pk_name}")

                    cur.execute("ALTER TABLE message_log ADD COLUMN id SERIAL PRIMARY KEY")
                    logger.info("Added id column (SERIAL PRIMARY KEY) to message_log")
                except psycopg2.errors.DuplicateColumn:
                    conn.rollback()
                    logger.info("Column id already exists in message_log")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to add id column: {e}")

    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
