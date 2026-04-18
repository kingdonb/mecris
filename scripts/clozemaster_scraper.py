#!/usr/bin/env python3
"""
Clozemaster Scraper - Extract review counts for Beeminder Reviewstack goals.
This script simulates a login to Clozemaster and scrapes the dashboard for review counts.
"""

import os
import sys
import logging
import json
import httpx
import asyncio
import html
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, date
from typing import Dict, Optional, List, Any
from dotenv import load_dotenv

# Add project root to path for local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Beeminder Client
from beeminder_client import BeeminderClient

from services.encryption_service import EncryptionService
from usage_tracker import UsageTracker

load_dotenv()
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("mecris.clozemaster")
logging.basicConfig(level=getattr(logging, log_level))

# Suppress verbose httpx logging which can leak tokens in URLs
logging.getLogger("httpx").setLevel(logging.WARNING)

class ClozemasterScraper:
    def __init__(self, user_id: str = None):
        self.user_id = user_id
        self.email = None
        self.password = None
        self.base_url = "https://www.clozemaster.com"
        self.csrf_token = ""
        self.cookies = {}
        # Real-looking User-Agent from a browser
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        }
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=self.headers)
        self.encryption = EncryptionService()
        self.tracker = UsageTracker()

    async def _load_credentials(self):
        """Fetch and decrypt credentials from Neon."""
        target_user_id = self.tracker.resolve_user_id(self.user_id)
        neon_url = os.getenv("NEON_DB_URL")
        
        if not neon_url:
            self.email = os.getenv("CLOZEMASTER_EMAIL")
            self.password = os.getenv("CLOZEMASTER_PASSWORD")
            if self.email and self.password:
                logger.warning(f"Using legacy CLOZEMASTER_EMAIL env var for user {target_user_id}")
                return
            raise RuntimeError("NEON_DB_URL not set and legacy env vars missing")

        try:
            import psycopg2
            with psycopg2.connect(neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT clozemaster_email_encrypted, clozemaster_password_encrypted FROM users WHERE pocket_id_sub = %s",
                        (target_user_id,)
                    )
                    row = cur.fetchone()
                    if row and row[0] and row[1]:
                        self.email = self.encryption.decrypt(row[0])
                        self.password = self.encryption.decrypt(row[1])
                        logger.info(f"Loaded encrypted Clozemaster credentials for user {target_user_id}")
                    else:
                        self.email = os.getenv("CLOZEMASTER_EMAIL")
                        self.password = os.getenv("CLOZEMASTER_PASSWORD")
                        if not (self.email and self.password):
                            raise RuntimeError(f"No Clozemaster credentials found in DB or ENV for user {target_user_id}")
                        logger.warning(f"Falling back to legacy env vars for user {target_user_id}")
        except Exception as e:
            logger.error(f"Failed to load Clozemaster credentials: {e}")
            raise

    async def login(self) -> bool:
        """Simulate login to Clozemaster and establish a session."""
        if not self.email or not self.password:
            await self._load_credentials()
            
        try:
            # 1. Get login page to extract CSRF token
            logger.info("Fetching login page...")
            resp = await self.client.get(f"{self.base_url}/login")
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Diagnostic: List all input fields
            inputs = soup.find_all('input')
            input_names = [i.get('name') for i in inputs if i.get('name')]
            
            csrf_elem = soup.find('input', {'name': 'authenticity_token'})
            if csrf_elem:
                self.csrf_token = csrf_elem['value']
            
            if not self.csrf_token:
                logger.warning("CSRF token not found, login might fail")
                
            # 2. Post login credentials
            user_field = "user[login]" if "user[login]" in input_names else "user[email]"
            
            login_data = {
                user_field: self.email,
                "user[password]": self.password,
                "authenticity_token": self.csrf_token,
                "commit": "Log In"
            }
            
            logger.info(f"Submitting login (using {user_field})...")
            resp = await self.client.post(f"{self.base_url}/login", data=login_data)
            
            # Check for specific success indicators in the resulting page
            success = "dashboard" in str(resp.url) or "Dashboard" in resp.text
            
            if success:
                logger.info("Login successful!")
                # Extract cookies for subsequent API calls
                self.cookies = {k: v for k, v in resp.cookies.items()}
                return True
            else:
                logger.error(f"Login failed (Status: {resp.status_code}, URL: {resp.url})")
                return False
                
        except Exception as e:
            logger.error(f"Error during Clozemaster login: {e}")
            return False

    async def get_review_forecast(self, lang_slug: str) -> Dict[str, Any]:
        """Scrape the review forecast and progress for a specific language from React props."""
        data_out = {"today": 0, "tomorrow": 0, "next_7_days": 0, "points": 0, "mastery": 0.0}
        
        try:
            # The dashboard contains all the data in a React prop
            resp = await self.client.get(f"{self.base_url}/dashboard", cookies=self.cookies)
            if resp.status_code != 200:
                logger.error(f"Could not load dashboard (Status: {resp.status_code})")
                return data_out
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Extract fresh CSRF token from the meta tag
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            if csrf_meta:
                self.csrf_token = csrf_meta['content']
                logger.info("Extracted fresh CSRF token from dashboard meta")

            dashboard_div = soup.find('div', {'data-react-class': 'DashboardV5'})
            if not dashboard_div:
                logger.error("Could not find DashboardV5 React component")
                return data_out
                
            props_json = html.unescape(dashboard_div['data-react-props'])
            data = json.loads(props_json)
            
            pairings = data.get("languagePairings", [])
            for pair in pairings:
                if pair.get("slug") == lang_slug:
                    data_out["today"] = pair.get("numReadyForReview", 0)
                    # 'score' is cumulative total points
                    data_out["points"] = pair.get("score", 0)
                    # 'numPointsToday' is a direct activity metric
                    data_out["points_today"] = pair.get("numPointsToday", 0)

                    logger.info(f"Found {lang_slug}: count={data_out['today']}, score={data_out['points']}, today={data_out['points_today']}")
                    logger.debug(f"All available pairing keys for {lang_slug}: {sorted(pair.keys())}")
                    
                    # LP ID for future API calls
                    lp_id = pair.get("id")
                    if lp_id:
                        await self._enrich_with_api_forecast(lp_id, data_out, lang_slug)
                    
                    return data_out
            
            return data_out
        except Exception as e:
            logger.warning(f"Could not retrieve data for {lang_slug}: {e}")
            return data_out

    async def _enrich_with_api_forecast(self, lp_id: int, forecast: Dict[str, Any], lang_slug: str):
        """Call the private API to get the tomorrow/7day forecast with proper headers."""
        try:
            # Precise headers from successful browser curl
            headers = {
                "Accept": "*/*",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.base_url}/l/{lang_slug}",
                "X-CSRF-Token": self.csrf_token,
                "Time-Zone-Offset-Hours": "-4",
                "sec-ch-ua-platform": '"macOS"',
                "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
                "sec-ch-ua-mobile": "?0"
            }

            api_url = f"{self.base_url}/api/v1/lp/{lp_id}/more-stats"
            resp = await self.client.get(api_url, headers=headers, cookies=self.cookies)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Successfully retrieved more-stats for LP {lp_id}")
                logger.debug(f"All top-level keys in more-stats response for LP {lp_id}: {sorted(data.keys())}")
                
                # Use the identified key
                forecast_data = data.get("reviewForecast", [])
                
                # Extract actual card count for today from ttmNumPlayedByDate
                ttm_played = data.get("ttmNumPlayedByDate", [])
                stats_per_day = data.get("statsPerDay", [])
                today_str = date.today().isoformat()
                cards_today = 0

                # Debug: Show today's entry in statsPerDay if it exists
                for entry in stats_per_day:
                    if entry.get("date") == today_str:
                        logger.debug(f"[{lang_slug}] statsPerDay for today: {entry}")
                        # If numCorrect is available, it might be the better metric
                        # cards_today = entry.get("numCorrect", 0) 
                        break

                # Debug: Show the date we are looking for and the end of the list
                if ttm_played:
                    logger.debug(f"[{lang_slug}] Looking for cards on {today_str}")
                
                for entry in ttm_played:
                    if entry.get("date") == today_str:
                        cards_today = entry.get("numPlayed", 0)
                        break
                
                # If we found a direct card count, we can store it
                if cards_today > 0:
                    forecast["cards_today"] = cards_today
                    logger.info(f"[{lang_slug}] Found actual card count for today: {cards_today}")
                
                if forecast_data:
                    # Clozemaster reviewForecast starts with Tomorrow at index 0
                    try:
                        if len(forecast_data) > 0:
                            # Index 0 is Tomorrow
                            tomorrow_data = forecast_data[0]
                            forecast["tomorrow"] = tomorrow_data.get("count", 0) if isinstance(tomorrow_data, dict) else tomorrow_data
                            
                            # Next 7 days liability (Tomorrow through +7 days)
                            forecast["next_7_days"] = sum(
                                d.get("count", 0) if isinstance(d, dict) else d 
                                for d in forecast_data[:7]
                            )
                            logger.info(f"Forecast for {lang_slug}: Tomorrow={forecast['tomorrow']}, 7-day={forecast['next_7_days']}")
                    except Exception as e:
                        logger.warning(f"Error parsing reviewForecast for {lang_slug}: {e}")
            else:
                logger.warning(f"API call for LP {lp_id} failed (Status: {resp.status_code})")
        except Exception as e:
            logger.warning(f"Error enriching forecast for LP {lp_id}: {e}")

    async def close(self):
        await self.client.aclose()

async def sync_clozemaster_to_beeminder(dry_run: bool = False, user_id: str = None):
    """Main task to scrape and push to Beeminder."""
    scraper = ClozemasterScraper(user_id=user_id)
    beeminder = BeeminderClient()
    
    # Pre-fetch required IDs for Neon persistence
    target_user_id = scraper.tracker.resolve_user_id(user_id)
    neon_url = os.getenv("NEON_DB_URL")
    
    try:
        if await scraper.login():
            # Language configuration
            languages = {
                "arabic": {"slug": "ara-eng", "goal": "reviewstack", "push_to_beeminder": True},
                "greek": {"slug": "ell-eng", "goal": "ellinika", "push_to_beeminder": False} # Odometer goal
            }
            
            # Fetch today's date in Eastern Time for Beeminder datapoint checks
            import zoneinfo
            eastern = zoneinfo.ZoneInfo("US/Eastern")
            today_eastern = datetime.now(eastern).replace(hour=0, minute=0, second=0, microsecond=0)

            # Pre-fetch all goals to check existence
            all_goals = await beeminder.get_all_goals()
            existing_slugs = {g["slug"] for g in all_goals}
            
            results = {}
            for name, config in languages.items():
                scraper_data = await scraper.get_review_forecast(config["slug"])
                count = scraper_data["today"]
                goal_slug = config["goal"]
                
                results[name] = {
                    "count": count, 
                    "forecast": scraper_data,
                    "points": scraper_data.get("points", 0),
                    "points_today": scraper_data.get("points_today", 0),
                    "mastery": scraper_data.get("mastery", 0.0)
                }
                
                # Map specific keys expected by LanguageSyncService
                results[name]["forecast"]["cards_today"] = scraper_data.get("cards_today", 0)
                results[name]["forecast"]["tomorrow"] = scraper_data.get("tomorrow", 0)
                results[name]["forecast"]["next_7_days"] = scraper_data.get("next_7_days", 0)

                logger.info(f"Scraped {name}: {count} reviews ready, {results[name]['points']} points")
                
                if dry_run:
                    logger.info(f"[DRY RUN] Would push {count} to {goal_slug}")
                    continue

                if not config.get("push_to_beeminder", True):
                    logger.info(f"Skipping Beeminder push for {name} (odometer goal)")
                    continue

                if goal_slug not in existing_slugs:
                    logger.warning(f"⚠️ Goal {goal_slug} does not exist on Beeminder. Skipping push for {name}.")
                    continue
                
                logger.info(f"Pushing {name} count ({count}) to Beeminder goal {goal_slug}...")

                # Deterministic requestid lets Beeminder upsert rather than insert on retries.
                # Format: {goal_slug}-{YYYY-MM-DD} ensures exactly one datapoint per goal per day.
                requestid = f"{goal_slug}-{today_eastern.strftime('%Y-%m-%d')}"

                # Predictable Liabilities note
                comment = f"Auto-synced from Clozemaster ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
                if scraper_data.get("tomorrow", 0) > 0:
                    comment += f" | Tomorrow liability: {scraper_data['tomorrow']}"
                if scraper_data.get("next_7_days", 0) > 0:
                    comment += f" | 7-day liability: {scraper_data['next_7_days']}"

                success = await beeminder.add_datapoint(
                    goal_slug,
                    float(count),
                    comment=comment,
                    requestid=requestid,
                )
                
                if success:
                    logger.info(f"✅ {name} sync complete")
                    # Persist to Neon for local observability parity
                    if neon_url:
                        try:
                            import psycopg2
                            with psycopg2.connect(neon_url) as conn:
                                with conn.cursor() as cur:
                                    cur.execute("""
                                        INSERT INTO language_stats (user_id, language_name, current_reviews, tomorrow_reviews, next_7_days_reviews, beeminder_slug, daily_completions, last_updated)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                                        ON CONFLICT (user_id, language_name) DO UPDATE SET
                                            current_reviews = EXCLUDED.current_reviews,
                                            tomorrow_reviews = EXCLUDED.tomorrow_reviews,
                                            next_7_days_reviews = EXCLUDED.next_7_days_reviews,
                                            beeminder_slug = EXCLUDED.beeminder_slug,
                                            daily_completions = EXCLUDED.daily_completions,
                                            last_updated = CURRENT_TIMESTAMP
                                    """, (
                                        target_user_id, 
                                        name.upper(), 
                                        count, 
                                        scraper_data.get("tomorrow", 0), 
                                        scraper_data.get("next_7_days", 0), 
                                        goal_slug, 
                                        scraper_data.get("cards_today", scraper_data.get("points_today", 0))
                                    ))
                                    conn.commit()
                        except Exception as e:
                            logger.error(f"Failed to persist {name} stats to Neon: {e}")
                else:
                    logger.error(f"❌ {name} sync failed")
            
            return results
        else:
            logger.error("Sync aborted due to login failure")
            return None
            
    finally:
        await scraper.close()
        await beeminder.close()

if __name__ == "__main__":
    import sys
    is_dry_run = "--dry-run" in sys.argv
    asyncio.run(sync_clozemaster_to_beeminder(dry_run=is_dry_run))
