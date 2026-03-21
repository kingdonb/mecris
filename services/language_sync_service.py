import os
import logging
import psycopg2
import asyncio
from typing import Dict, Any, Optional, List
from scripts.clozemaster_scraper import sync_clozemaster_to_beeminder

logger = logging.getLogger("mecris.services.language_sync")

class LanguageSyncService:
    """
    Consolidated service for syncing Clozemaster stats to Beeminder and Neon DB.
    """
    
    def __init__(self, beeminder_client):
        self.beeminder_client = beeminder_client
        self.neon_url = os.getenv("NEON_DB_URL")
        
        # Mapping from scraper keys to Beeminder slugs
        self.lang_to_slug = {
            "ARABIC": "reviewstack",
            "GREEK": "reviewstack-greek"
        }

    def _update_neon_db(self, scraper_data: Dict, goal_map: Dict, summary: Dict) -> None:
        """Synchronous helper method to update Neon DB."""
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    for lang, data in scraper_data.items():
                        name = lang.upper()
                        count = data.get("count", 0)
                        forecast = data.get("forecast", {})
                        tomorrow = forecast.get("tomorrow", 0)
                        next_7 = forecast.get("next_7_days", 0)
                        
                        # Default values
                        safebuf = 0
                        derail_risk = 'SAFE'
                        daily_rate = 0.0
                        pump_multiplier = 1.0
                        
                        # Try to match goal
                        slug = self.lang_to_slug.get(name)
                        # Fallback/Override for Greek
                        if name == "GREEK" and "ellinika" in goal_map:
                            slug = "ellinika"
                            
                        if slug and slug in goal_map:
                            goal = goal_map[slug]
                            safebuf = goal.get("safebuf", 0)
                            derail_risk = goal.get("derail_risk", "SAFE")
                            daily_rate = goal.get("rate", 0.0)
                            summary["min_safebuf"] = min(summary["min_safebuf"], safebuf)

                        # Fetch existing multiplier if any
                        cur.execute("SELECT pump_multiplier FROM language_stats WHERE language_name = %s", (name,))
                        row = cur.fetchone()
                        if row:
                            pump_multiplier = float(row[0])
                        
                        cur.execute("""
                            INSERT INTO language_stats (language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, daily_rate, safebuf, derail_risk, pump_multiplier)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (language_name) DO UPDATE SET
                                current_reviews = EXCLUDED.current_reviews,
                                tomorrow_reviews = EXCLUDED.tomorrow_reviews,
                                next_7_days_reviews = EXCLUDED.next_7_days_reviews,
                                daily_rate = EXCLUDED.daily_rate,
                                safebuf = EXCLUDED.safebuf,
                                derail_risk = EXCLUDED.derail_risk,
                                pump_multiplier = EXCLUDED.pump_multiplier,
                                last_updated = CURRENT_TIMESTAMP
                        """, (name, count, tomorrow, next_7, daily_rate, safebuf, derail_risk, pump_multiplier))
                        
                        summary[lang] = {
                            "count": count,
                            "safebuf": safebuf,
                            "derail_risk": derail_risk,
                            "pump_multiplier": pump_multiplier
                        }
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to update Neon DB with language stats: {e}")
            summary["db_error"] = str(e)

    async def sync_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Perform a full sync: Scrape -> Beeminder (if not dry_run) -> Neon.
        Returns a summary of the sync.
        """
        try:
            # 1. Scrape and push to Beeminder
            scraper_data = await sync_clozemaster_to_beeminder(dry_run=dry_run)
            if not scraper_data:
                return {"success": False, "error": "No data returned from scraper"}

            # 2. Fetch fresh Beeminder goals to get safebuf and derail_risk
            all_goals = await self.beeminder_client.get_all_goals()
            goal_map = {g.get("slug"): g for g in all_goals}
            
            summary = {
                "success": True,
                "min_safebuf": 999,
                "sync_time": os.getenv("CURRENT_TIME", ""), # for testing/logging
            }

            # 3. Update Neon DB
            if self.neon_url:
                await asyncio.to_thread(self._update_neon_db, scraper_data, goal_map, summary)
            
            return summary

        except Exception as e:
            logger.error(f"Language sync service failed: {e}")
            return {"success": False, "error": str(e)}
