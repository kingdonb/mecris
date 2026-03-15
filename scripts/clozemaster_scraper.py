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
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dotenv import load_dotenv

# Add project root to path for local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Beeminder Client
from beeminder_client import BeeminderClient

load_dotenv()
logger = logging.getLogger("mecris.clozemaster")
logging.basicConfig(level=logging.INFO)

class ClozemasterScraper:
    def __init__(self):
        self.email = os.getenv("CLOZEMASTER_EMAIL")
        self.password = os.getenv("CLOZEMASTER_PASSWORD")
        self.base_url = "https://www.clozemaster.com"
        self.csrf_token = ""
        # Real-looking User-Agent to avoid scraping blocks
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers)
        
    async def login(self) -> bool:
        """Simulate login to Clozemaster and establish a session."""
        if not self.email or not self.password:
            logger.error("CLOZEMASTER_EMAIL or CLOZEMASTER_PASSWORD not set")
            return False
            
        try:
            # 1. Get login page to extract CSRF token
            logger.info("Fetching login page...")
            resp = await self.client.get(f"{self.base_url}/login")
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Diagnostic: List all input fields
            inputs = soup.find_all('input')
            input_names = [i.get('name') for i in inputs if i.get('name')]
            logger.info(f"Found input fields: {input_names}")
            
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
                return True
            else:
                logger.error(f"Login failed (Status: {resp.status_code}, URL: {resp.url})")
                return False
                
        except Exception as e:
            logger.error(f"Error during Clozemaster login: {e}")
            return False

    async def get_review_forecast(self, lang_slug: str) -> Dict[str, int]:
        """Scrape the review forecast for a specific language from React props."""
        forecast = {"today": 0, "tomorrow": 0, "next_7_days": 0}
        
        try:
            # The dashboard contains all the data in a React prop
            resp = await self.client.get(f"{self.base_url}/dashboard")
            if resp.status_code != 200:
                logger.error(f"Could not load dashboard (Status: {resp.status_code})")
                return forecast
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            dashboard_div = soup.find('div', {'data-react-class': 'DashboardV5'})
            if not dashboard_div:
                logger.error("Could not find DashboardV5 React component")
                return forecast
                
            props_json = html.unescape(dashboard_div['data-react-props'])
            data = json.loads(props_json)
            
            pairings = data.get("languagePairings", [])
            for pair in pairings:
                if pair.get("slug") == lang_slug:
                    forecast["today"] = pair.get("numReadyForReview", 0)
                    logger.info(f"Found {lang_slug} count in React props: {forecast['today']}")
                    
                    # LP ID for future API calls
                    lp_id = pair.get("id")
                    if lp_id:
                        # Attempt to enrich with forecast, but don't fail if it doesn't work
                        await self._enrich_with_api_forecast(lp_id, forecast)
                    
                    return forecast
        except Exception as e:
            logger.warning(f"Could not retrieve forecast for {lang_slug}: {e}")
            return forecast

    async def _enrich_with_api_forecast(self, lp_id: int, forecast: Dict[str, int]):
        """Call the private API to get the tomorrow/7day forecast with proper headers."""
        try:
            headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.base_url}/dashboard",
                "X-CSRF-Token": self.csrf_token
            }

            api_url = f"{self.base_url}/api/v1/lp/{lp_id}/more-stats"
            resp = await self.client.get(api_url, headers=headers)
            
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Successfully retrieved more-stats for LP {lp_id}")
                
                # Try to extract forecast data
                reviews_by_day = data.get("reviews_by_day", []) or data.get("forecast", [])
                
                if reviews_by_day and len(reviews_by_day) > 1:
                    # tomorrow is index 1 if index 0 is today
                    tomorrow_data = reviews_by_day[1]
                    if isinstance(tomorrow_data, dict):
                        forecast["tomorrow"] = tomorrow_data.get("count", 0)
                    else:
                        forecast["tomorrow"] = tomorrow_data
                    
                    # Next 7 days
                    try:
                        forecast["next_7_days"] = sum(
                            d.get("count", 0) if isinstance(d, dict) else d 
                            for d in reviews_by_day[:7]
                        )
                    except: pass
                    
                    logger.info(f"Forecast for LP {lp_id}: Tomorrow={forecast['tomorrow']}, 7-day={forecast['next_7_days']}")
            else:
                logger.warning(f"API call for LP {lp_id} failed (Status: {resp.status_code})")
        except Exception as e:
            logger.warning(f"Error enriching forecast for LP {lp_id}: {e}")

    async def close(self):
        await self.client.aclose()

async def sync_clozemaster_to_beeminder(dry_run: bool = False):
    """Main task to scrape and push to Beeminder."""
    scraper = ClozemasterScraper()
    beeminder = BeeminderClient()
    
    try:
        if await scraper.login():
            # Language configuration
            languages = {
                "arabic": {"slug": "ara-eng", "goal": "reviewstack"},
                "greek": {"slug": "ell-eng", "goal": "reviewstack-greek"}
            }
            
            # Pre-fetch all goals to check existence
            all_goals = await beeminder.get_all_goals()
            existing_slugs = {g["slug"] for g in all_goals}
            
            results = {}
            for name, config in languages.items():
                forecast = await scraper.get_review_forecast(config["slug"])
                count = forecast["today"]
                goal_slug = config["goal"]
                
                results[name] = {"count": count, "forecast": forecast}
                logger.info(f"Scraped {name}: {count} reviews ready")
                
                if dry_run:
                    logger.info(f"[DRY RUN] Would push {count} to {goal_slug}")
                    continue

                if goal_slug not in existing_slugs:
                    logger.warning(f"⚠️ Goal {goal_slug} does not exist on Beeminder. Skipping push.")
                    continue

                logger.info(f"Pushing {name} count ({count}) to Beeminder goal {goal_slug}...")
                
                # Predictable Liabilities note
                comment = f"Auto-synced from Clozemaster ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
                if forecast.get("tomorrow", 0) > 0:
                    comment += f" | Tomorrow liability: {forecast['tomorrow']}"

                success = await beeminder.add_datapoint(
                    goal_slug, 
                    float(count), 
                    comment=comment
                )
                
                if success:
                    logger.info(f"✅ {name} sync complete")
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
