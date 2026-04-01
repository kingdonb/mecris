#!/usr/bin/env python3
"""
Groq Usage Scraper - Web scraping approach for Groq billing data

IMPORTANT: This is a temporary solution until Groq releases a billing API.
Use sparingly to avoid ToS issues. Cache results aggressively.
"""

"""
Groq Usage Scraper (Proof of Concept)

NOTE: This scraper is difficult to maintain due to Groq's use of Google SSO 
and the lack of an official billing API. We intentionally avoid importing 
private APIs or extensive scraping where possible.
Reference: https://community.groq.com/t/add-api-endpoint-to-fetch-billing-and-usage-data/378
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from playwright.sync_api import sync_playwright

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("groq_scraper")

class GroqUsageScraper:
    def __init__(self, cache_minutes: int = 15):
        self.cache_minutes = cache_minutes
        self.neon_url = os.getenv("NEON_DB_URL")
        
        # Groq credentials from environment
        self.email = os.getenv('GROQ_EMAIL')
        self.password = os.getenv('GROQ_PASSWORD')
        
        if not self.email or not self.password:
            logger.warning("GROQ_EMAIL or GROQ_PASSWORD not set - scraper will not work")
        
        if not self.neon_url:
            logger.error("NEON_DB_URL not set - caching will not work")
    
    def get_cached_usage(self) -> Optional[Dict]:
        """Get cached usage data if still valid."""
        if not self.neon_url:
            return None
            
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT cache_data, expires_at FROM provider_cache 
                        WHERE provider = %s AND cache_key = %s
                        AND expires_at > %s
                    """, ("groq", "usage_data", datetime.now()))
                    row = cur.fetchone()
                    if row:
                        logger.info("Using cached Groq usage data (Neon)")
                        return json.loads(row['cache_data'])
        except Exception as e:
            logger.error(f"Neon cache read failed: {e}")
        
        return None
    
    def cache_usage_data(self, data: Dict) -> None:
        """Cache usage data with expiration."""
        if not self.neon_url:
            return
            
        expires_at = datetime.now() + timedelta(minutes=self.cache_minutes)
        try:
            import psycopg2
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO provider_cache (provider, cache_key, cache_data, cached_at, expires_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (provider, cache_key) DO UPDATE SET
                            cache_data = EXCLUDED.cache_data,
                            cached_at = EXCLUDED.cached_at,
                            expires_at = EXCLUDED.expires_at
                    """, ("groq", "usage_data", json.dumps(data), datetime.now(), expires_at))
            logger.info(f"Cached Groq usage data until {expires_at} (Neon)")
        except Exception as e:
            logger.error(f"Neon cache write failed: {e}")
    
    def scrape_usage_data(self) -> Dict:
        """Scrape Groq usage data using Playwright."""
        if not self.email or not self.password:
            return {
                "success": False,
                "error": "Missing credentials - set GROQ_EMAIL and GROQ_PASSWORD",
                "source": "scraper"
            }
        
        logger.info("Starting Groq usage scraping (use sparingly!)")
        
        try:
            with sync_playwright() as p:
                # Launch browser
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                
                page = context.new_page()
                
                # Navigate to login page
                logger.info("Navigating to Groq console")
                page.goto("https://console.groq.com/login", wait_until="networkidle")
                
                # Login
                logger.info("Attempting login")
                page.fill("input[type='email'], input[name='email']", self.email)
                page.fill("input[type='password'], input[name='password']", self.password)
                page.click("button[type='submit'], button:has-text('Sign in')")
                
                # Wait for login to complete
                page.wait_for_load_state("networkidle", timeout=10000)
                
                # Navigate to usage page
                logger.info("Navigating to usage page")
                page.goto("https://console.groq.com/usage", wait_until="networkidle")
                
                # Extract usage data (these selectors may need updating)
                usage_data = {}
                
                try:
                    # Look for common usage display patterns
                    usage_selectors = [
                        "[data-testid*='usage']",
                        ".usage-amount",
                        ".billing-amount",
                        ".cost-display",
                        "span:has-text('$')",
                        "div:has-text('Total')"
                    ]
                    
                    for selector in usage_selectors:
                        try:
                            elements = page.query_selector_all(selector)
                            for i, element in enumerate(elements):
                                text = element.inner_text().strip()
                                if '$' in text:
                                    usage_data[f"amount_{i}"] = text
                                    logger.info(f"Found usage amount: {text}")
                        except:
                            continue
                    
                    # Try to extract monthly total
                    monthly_selectors = [
                        "span:has-text('This month')",
                        ".monthly-usage",
                        "[data-testid='monthly-cost']"
                    ]
                    
                    for selector in monthly_selectors:
                        try:
                            element = page.query_selector(selector)
                            if element:
                                # Look for nearby dollar amounts
                                parent = element.query_selector('xpath=..')
                                if parent:
                                    text = parent.inner_text()
                                    if '$' in text:
                                        usage_data["monthly_usage"] = text
                                        break
                        except:
                            continue
                    
                    # Fallback: grab all text that looks like dollar amounts
                    if not usage_data:
                        page_text = page.inner_text("body")
                        import re
                        dollar_amounts = re.findall(r'\$\d+\.?\d*', page_text)
                        if dollar_amounts:
                            usage_data["detected_amounts"] = dollar_amounts
                            logger.info(f"Detected dollar amounts: {dollar_amounts}")
                
                except Exception as e:
                    logger.warning(f"Data extraction error: {e}")
                    # Take screenshot for debugging
                    page.screenshot(path="/tmp/groq_usage_debug.png")
                    logger.info("Screenshot saved to /tmp/groq_usage_debug.png")
                
                browser.close()
                
                if usage_data:
                    result = {
                        "success": True,
                        "data": usage_data,
                        "scraped_at": datetime.now().isoformat(),
                        "source": "scraper"
                    }
                    logger.info(f"Successfully scraped Groq usage: {usage_data}")
                else:
                    result = {
                        "success": False,
                        "error": "No usage data found - selectors may need updating",
                        "source": "scraper"
                    }
                    logger.warning("No usage data found during scraping")
                
                return result
                
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "scraper"
            }
    
    def get_usage_data(self) -> Dict:
        """Get Groq usage data, using cache when possible."""
        # Try cache first
        cached_data = self.get_cached_usage()
        if cached_data:
            return {
                **cached_data,
                "cached": True,
                "cache_age_minutes": self._get_cache_age_minutes(cached_data.get('scraped_at'))
            }
        
        # Cache miss or expired - scrape new data
        logger.info("Cache miss - scraping fresh Groq usage data")
        scraped_data = self.scrape_usage_data()
        
        if scraped_data.get("success"):
            self.cache_usage_data(scraped_data)
        
        return {
            **scraped_data,
            "cached": False
        }
    
    def _get_cache_age_minutes(self, scraped_at: str) -> int:
        """Calculate cache age in minutes."""
        try:
            scraped_time = datetime.fromisoformat(scraped_at.replace('Z', '+00:00'))
            age = datetime.now() - scraped_time.replace(tzinfo=None)
            return int(age.total_seconds() / 60)
        except:
            return 0

def fetch_groq_usage() -> Dict:
    """Main function for fetching Groq usage data."""
    scraper = GroqUsageScraper()
    return scraper.get_usage_data()

if __name__ == "__main__":
    # Test the scraper
    print("=== Groq Usage Scraper Test ===")
    result = fetch_groq_usage()
    print(json.dumps(result, indent=2))
