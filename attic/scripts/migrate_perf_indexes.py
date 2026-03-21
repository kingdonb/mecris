import os
import psycopg2
import logging
from dotenv import load_dotenv

load_dotenv()
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
                logger.info("Adding performance indexes to walk_inferences...")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_walk_status ON walk_inferences(status);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_walk_start_time ON walk_inferences (start_time);")
                conn.commit()
                logger.info("Indexes added successfully!")
    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
