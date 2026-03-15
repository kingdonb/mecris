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

    async def get_review_counts(self) -> Dict[str, int]:
        """Scrape review counts for Arabic and Greek."""
        counts = {"arabic": 0, "greek": 0}
        
        try:
            # We scrape language specific pages for accuracy
            # Arabic: ara-eng, Greek: ell-eng (Verify these slugs)
            languages = {
                "arabic": "ara-eng",
                "greek": "ell-eng"
            }
            
            for lang, slug in languages.items():
                logger.info(f"Fetching {lang} review count...")
                url = f"{self.base_url}/languages/{slug}/manage"
                resp = await self.client.get(url)
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Search for "Ready for review" or "Review"
                # Looking for: <strong>123</strong> <span>Ready for review</span>
                review_text = soup.find(text=lambda t: "Ready for review" in str(t))
                if review_text:
                    # Number is usually in a strong tag nearby
                    parent = review_text.parent
                    strong = parent.find_previous('strong') or parent.find('strong')
                    if strong:
                        try:
                            count_str = strong.text.strip().replace(',', '')
                            counts[lang] = int(count_str)
                            logger.info(f"Found {lang} count: {counts[lang]}")
                        except:
                            logger.warning(f"Could not parse count for {lang}")
                else:
                    logger.warning(f"Could not find review text for {lang}")
                    
            return counts
            
        except Exception as e:
            logger.error(f"Error scraping review counts: {e}")
            return counts

    async def close(self):
        await self.client.aclose()

async def sync_clozemaster_to_beeminder():
    """Main task to scrape and push to Beeminder."""
    scraper = ClozemasterScraper()
    beeminder = BeeminderClient()
    
    try:
        if await scraper.login():
            counts = await scraper.get_review_counts()
            
            # Goal mapping
            # Arabiya -> reviewstack-arabic (example slug)
            # Greek -> reviewstack-greek (example slug)
            mapping = {
                "arabic": "reviewstack", # Existing goal
                "greek": "reviewstack-greek"
            }
            
            for lang, count in counts.items():
                goal_slug = mapping.get(lang)
                if goal_slug:
                    logger.info(f"Pushing {lang} count ({count}) to Beeminder goal {goal_slug}...")
                    # Note: These are 'Odometer' style or 'Goal' style? 
                    # If the goal is 'downward trend', we just push the current absolute number.
                    success = await beeminder.add_datapoint(
                        goal_slug, 
                        float(count), 
                        comment=f"Auto-synced from Clozemaster Scraper ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
                    )
                    if success:
                        logger.info(f"✅ {lang} sync complete")
                    else:
                        logger.error(f"❌ {lang} sync failed")
        else:
            logger.error("Sync aborted due to login failure")
            
    finally:
        await scraper.close()
        await beeminder.close()

if __name__ == "__main__":
    asyncio.run(sync_clozemaster_to_beeminder())
