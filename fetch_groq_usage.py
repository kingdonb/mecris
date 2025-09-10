#!/usr/bin/env python3
"""
Groq Usage Scraper - Web scraping approach for Groq billing data

IMPORTANT: This is a temporary solution until Groq releases a billing API.
Use sparingly to avoid ToS issues. Cache results aggressively.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from playwright.sync_api import sync_playwright
from virtual_budget_manager import VirtualBudgetManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("groq_scraper")

class GroqUsageScraper:
    def __init__(self, cache_minutes: int = 15):
        self.cache_minutes = cache_minutes
        self.budget_manager = VirtualBudgetManager()
        
        # Groq credentials from environment
        self.email = os.getenv('GROQ_EMAIL')
        self.password = os.getenv('GROQ_PASSWORD')
        
        if not self.email or not self.password:
            logger.warning("GROQ_EMAIL or GROQ_PASSWORD not set - scraper will not work")
    
    def get_cached_usage(self) -> Optional[Dict]:
        """Get cached usage data if still valid."""
        try:
            import sqlite3
            with sqlite3.connect(self.budget_manager.db_path) as conn:
                cursor = conn.execute("""
                    SELECT cache_data, cached_at FROM provider_cache 
                    WHERE provider = 'groq' AND cache_key = 'usage_data'
                    AND expires_at > ?
                """, (datetime.now().isoformat(),))
                
                result = cursor.fetchone()
                if result:
                    logger.info("Using cached Groq usage data")
                    return json.loads(result[0])
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        
        return None
    
    def cache_usage_data(self, data: Dict) -> None:
        """Cache usage data with expiration."""
        expires_at = datetime.now() + timedelta(minutes=self.cache_minutes)
        
        try:
            import sqlite3
            with sqlite3.connect(self.budget_manager.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO provider_cache 
                    (provider, cache_key, cache_data, cached_at, expires_at)
                    VALUES ('groq', 'usage_data', ?, ?, ?)
                """, (json.dumps(data), datetime.now().isoformat(), expires_at.isoformat()))
                
                logger.info(f"Cached Groq usage data until {expires_at}")
        except Exception as e:
            logger.error(f"Cache write error: {e}")
    
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
