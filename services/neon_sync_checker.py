import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import psycopg2
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("mecris.neon")

class NeonSyncChecker:
    """Checks the Cloud Neon DB for recent walk telemetry synced from the Android app."""

    def __init__(self):
        self.db_url = os.getenv("NEON_DB_URL")
        self.default_user_id = os.getenv("DEFAULT_USER_ID")
        if not self.db_url:
            logger.warning("NEON_DB_URL not configured. Cloud walk sync checks will be skipped.")

    def has_walk_today(self, user_id: str = None) -> bool:
        """
        Queries the Neon walk_inferences table for any walk starting today.
        Aligns 'today' to US/Eastern midnight.
        Correctly handles UTC-to-Eastern conversion for stored timestamps.
        """
        if not self.db_url:
            return False
            
        target_user_id = user_id or self.default_user_id

        try:
            # Connect to Neon
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()

            # Define 'today' in Eastern Time midnight
            import zoneinfo
            eastern = zoneinfo.ZoneInfo("US/Eastern")
            local_now = datetime.now(eastern)
            today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Convert stored UTC strings to TIMESTAMPTZ, then at time zone 'US/Eastern'
            # and compare with today_start at 00:00:00
            query = """
                SELECT COUNT(*) FROM walk_inferences 
                WHERE (start_time::TIMESTAMPTZ AT TIME ZONE 'US/Eastern') >= %s
            """
            params = [today_start.replace(tzinfo=None)] # AT TIME ZONE returns a naive timestamp in that zone

            if target_user_id:
                query += " AND user_id = %s"
                params.append(target_user_id)

            cur.execute(query, params)
            count = cur.fetchone()[0]

            cur.close()
            conn.close()

            logger.info(f"Neon walk check for {today_start}: found {count} walks")
            return count > 0

        except Exception as e:
            logger.error(f"Failed to query Neon for walk data: {e}")
            return False

    def get_latest_walk(self, user_id: str = None):
        """Fetches the most recent walk record for the user."""
        if not self.db_url:
            return None
            
        target_user_id = user_id or self.default_user_id

        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()

            query = "SELECT start_time::TIMESTAMPTZ, step_count, distance_meters, distance_source FROM walk_inferences"
            params = []
            
            if target_user_id:
                query += " WHERE user_id = %s"
                params.append(target_user_id)
            
            query += " ORDER BY start_time DESC LIMIT 1"

            cur.execute(query, params)
            row = cur.fetchone()

            cur.close()
            conn.close()

            if row:
                return {
                    "start_time": row[0],
                    "step_count": row[1],
                    "distance_meters": row[2],
                    "distance_source": row[3]
                }
            return None

        except Exception as e:
            logger.error(f"Failed to fetch latest walk from Neon: {e}")
            return None

    def get_language_stats(self, user_id: str = None) -> Dict[str, Any]:
        """Fetches all rows from language_stats table for the user."""
        if not self.db_url:
            return {}
            
        target_user_id = user_id or self.default_user_id

        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()

            cur.execute("SELECT language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, pump_multiplier FROM language_stats WHERE user_id = %s", (target_user_id,))
            rows = cur.fetchall()

            cur.close()
            conn.close()

            stats = {}
            for row in rows:
                stats[row[0].lower()] = {
                    "current": row[1],
                    "tomorrow": row[2],
                    "next_7_days": row[3],
                    "multiplier": float(row[4]) if row[4] is not None else 1.0
                }
            return stats

        except Exception as e:
            logger.error(f"Failed to fetch language stats from Neon: {e}")
            return {}

    def update_pump_multiplier(self, language_name: str, multiplier: float, user_id: str = None) -> bool:
        """Updates the pump_multiplier for a specific language and user."""
        if not self.db_url:
            return False
            
        target_user_id = user_id or self.default_user_id

        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()

            cur.execute("""
                UPDATE language_stats 
                SET pump_multiplier = %s 
                WHERE language_name = %s AND user_id = %s
            """, (multiplier, language_name.upper(), target_user_id))
            
            conn.commit()
            cur.close()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Failed to update pump_multiplier in Neon: {e}")
            return False
