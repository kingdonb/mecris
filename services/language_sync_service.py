import os
import logging
import psycopg2
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import zoneinfo
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
            "GREEK": "ellinika"
        }

    def _update_neon_db(self, scraper_data: Dict, goal_map: Dict, summary: Dict, user_id: str) -> None:
        """Synchronous helper method to update Neon DB."""
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    for lang, data in scraper_data.items():
                        name = lang.upper()
                        count = data.get("count", 0)
                        points = data.get("points", 0)
                        forecast = data.get("forecast", {})
                        tomorrow = forecast.get("tomorrow", 0)
                        next_7 = forecast.get("next_7_days", 0)
                        
                        # Fetch existing stats to calculate progress
                        cur.execute("SELECT last_points, daily_completions, last_updated FROM language_stats WHERE user_id = %s AND language_name = %s", (user_id, name))
                        row = cur.fetchone()
                        
                        last_points = 0
                        daily_completions = 0
                        last_updated = None
                        
                        if row:
                            last_points = row[0] or 0
                            daily_completions = row[1] or 0
                            last_updated = row[2]

                        # Detect Day Boundary (US/Eastern)
                        eastern = zoneinfo.ZoneInfo("US/Eastern")
                        now_eastern = datetime.now(eastern)
                        if last_updated:
                            last_upd_eastern = last_updated.astimezone(eastern)
                            if now_eastern.date() > last_upd_eastern.date():
                                logger.info(f"Day boundary detected for {name}. Resetting daily completions.")
                                daily_completions = 0
                        
                        # Update completions if points increased
                        if points > last_points and last_points > 0:
                            diff = points - last_points
                            daily_completions += diff
                            logger.info(f"Detected {diff} new points for {name}. Total today: {daily_completions}")
                        
                        # Default values for goal stats
                        safebuf = 0
                        derail_risk = 'SAFE'
                        daily_rate = 0.0
                        
                        # Try to match goal
                        slug = self.lang_to_slug.get(name)
                        if name == "GREEK" and "ellinika" in goal_map:
                            slug = "ellinika"
                            
                        if slug and slug in goal_map:
                            goal = goal_map[slug]
                            safebuf = goal.get("safebuf", 0)
                            derail_risk = goal.get("derail_risk", "SAFE")
                            daily_rate = goal.get("rate", 0.0)
                            summary["min_safebuf"] = min(summary["min_safebuf"], safebuf)

                        cur.execute("""
                            INSERT INTO language_stats (user_id, language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, daily_rate, safebuf, derail_risk, beeminder_slug, daily_completions, last_points, total_points)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (user_id, language_name) DO UPDATE SET
                                current_reviews = EXCLUDED.current_reviews,
                                tomorrow_reviews = EXCLUDED.tomorrow_reviews,
                                next_7_days_reviews = EXCLUDED.next_7_days_reviews,
                                daily_rate = EXCLUDED.daily_rate,
                                safebuf = EXCLUDED.safebuf,
                                derail_risk = EXCLUDED.derail_risk,
                                beeminder_slug = EXCLUDED.beeminder_slug,
                                daily_completions = EXCLUDED.daily_completions,
                                last_points = EXCLUDED.last_points,
                                total_points = EXCLUDED.total_points,
                                last_updated = CURRENT_TIMESTAMP
                        """, (user_id, name, count, tomorrow, next_7, daily_rate, safebuf, derail_risk, slug, daily_completions, points, points))
                        
                        summary[lang] = {
                            "count": count,
                            "safebuf": safebuf,
                            "derail_risk": derail_risk,
                            "daily_completions": daily_completions
                        }
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to update Neon DB with language stats: {e}")
            summary["db_error"] = str(e)

    async def sync_all(self, dry_run: bool = False, user_id: str = None) -> Dict[str, Any]:
        """
        Perform a full sync: Scrape -> Beeminder (if not dry_run) -> Neon.
        Returns a summary of the sync.
        """
        target_user_id = user_id or os.getenv("DEFAULT_USER_ID")
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
                "sync_time": datetime.now().isoformat(),
            }

            # 3. Update Neon DB (Calculates completions from upstream points)
            if self.neon_url:
                await asyncio.to_thread(self._update_neon_db, scraper_data, goal_map, summary, target_user_id)
            
            return summary

        except Exception as e:
            logger.error(f"Language sync service failed: {e}")
            return {"success": False, "error": str(e)}
