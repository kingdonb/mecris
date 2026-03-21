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
                logger.info("Adding pump_multiplier to language_stats...")
                cur.execute("""
                    ALTER TABLE language_stats 
                    ADD COLUMN IF NOT EXISTS pump_multiplier NUMERIC(4, 1) DEFAULT 1.0
                """)
                conn.commit()
                logger.info("Migration successful!")
    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
