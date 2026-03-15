#!/usr/bin/env python3
"""
Clozemaster Scraper - Extract review counts for Beeminder Reviewstack goals.
This script simulates a login to Clozemaster and scrapes the dashboard for review counts.
"""

import os
import logging
import json
import httpx
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, Optional, List
from dotenv import load_dotenv

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
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        
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
            
            csrf_token = ""
            csrf_elem = soup.find('input', {'name': 'authenticity_token'})
            if csrf_elem:
                csrf_token = csrf_elem['value']
            
            if not csrf_token:
                logger.warning("CSRF token not found, login might fail")
                
            # 2. Post login credentials
            login_data = {
                "user[email]": self.email,
                "user[password]": self.password,
                "authenticity_token": csrf_token,
                "commit": "Log In"
            }
            
            logger.info("Submitting login...")
            resp = await self.client.post(f"{self.base_url}/login", data=login_data)
            
            if resp.status_code == 200 and "dashboard" in str(resp.url):
                logger.info("Login successful!")
                return True
            else:
                logger.error(f"Login failed (Status: {resp.status_code}, URL: {resp.url})")
                return False
                
        except Exception as e:
            logger.error(f"Error during Clozemaster login: {e}")
            return False

    async def get_review_forecast(self, lang_slug: str) -> Dict[str, int]:
        """Scrape the review forecast for a specific language."""
        forecast = {"today": 0, "tomorrow": 0, "next_7_days": 0}
        
        try:
            # Stats page often contains the review forecast charts
            url = f"{self.base_url}/languages/{lang_slug}/stats"
            resp = await self.client.get(url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # This logic is speculative until we see the exact Pro stats DOM
            # But we can look for text indicators of future dates
            logger.info(f"Analyzing {lang_slug} forecast data...")
            
            # Fallback to dashboard "Ready for review" if full stats scrape fails
            dashboard_count = await self._get_ready_count(lang_slug)
            forecast["today"] = dashboard_count
            
            return forecast
        except Exception as e:
            logger.warning(f"Could not retrieve full forecast for {lang_slug}: {e}")
            return forecast

    async def _get_ready_count(self, lang_slug: str) -> int:
        """Helper to get current review count from language manage page."""
        url = f"{self.base_url}/languages/{lang_slug}/manage"
        resp = await self.client.get(url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        review_text = soup.find(text=lambda t: "Ready for review" in str(t))
        if review_text:
            parent = review_text.parent
            strong = parent.find_previous('strong') or parent.find('strong')
            if strong:
                try:
                    return int(strong.text.strip().replace(',', ''))
                except: pass
        return 0

    async def close(self):
        await self.client.aclose()

async def sync_clozemaster_to_beeminder():
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
            
            for name, config in languages.items():
                forecast = await scraper.get_review_forecast(config["slug"])
                count = forecast["today"]
                goal_slug = config["goal"]
                
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
        else:
            logger.error("Sync aborted due to login failure")
            
    finally:
        await scraper.close()
        await beeminder.close()

if __name__ == "__main__":
    asyncio.run(sync_clozemaster_to_beeminder())
