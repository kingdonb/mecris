#!/usr/bin/env python3
"""
OpenRouter Usage Tracker - v2 with org-wide aggregation

Tracks both:
1. Daily request count (aggregated from per-key usage_daily via management key)
2. Dollar spend ($10 credit limit) - via OpenRouter API /api/v1/credits

Uses management key to poll org-wide usage, records to Neon for envelope tracking.
"""

import os
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Dict, Any, List
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

# Load .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

logger = logging.getLogger("mecris.openrouter_tracker")

class OpenRouterTracker:
    def __init__(
        self,
        neon_url: Optional[str] = None,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
        management_key: Optional[str] = None
    ):
        self.neon_url = neon_url or os.getenv("NEON_DB_URL")
        self.user_id = user_id or os.getenv("DEFAULT_USER_ID", "yebyen")
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.management_key = management_key or os.getenv("OPENROUTER_MANAGEMENT_KEY") or os.getenv("OPENROUTER_ADMIN_KEY")
        
        if not self.neon_url:
            logger.warning("NEON_DB_URL not set; OpenRouterTracker will fail on DB operations.")
        if not self.management_key:
            logger.warning("OPENROUTER_MANAGEMENT_KEY not set; org-wide daily request aggregation will fail.")
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set; dollar tracking will fail.")
            
        self.base_url = "https://openrouter.ai/api/v1"
        self._init_db()
    
    def _init_db(self):
        """Create tracking tables if they don't exist."""
        if not self.neon_url:
            return
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    # Dollar spend tracking (synced from OpenRouter /credits)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS openrouter_dollar_spend (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            total_credits NUMERIC(10,2) NOT NULL,
                            total_usage NUMERIC(10,6) NOT NULL,
                            remaining_credits NUMERIC(10,6) NOT NULL,
                            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                        CREATE INDEX IF NOT EXISTS idx_openrouter_dollar_spend_user_time
                            ON openrouter_dollar_spend (user_id, recorded_at);
                    """)
                    
                    # Aggregated daily request count (org-wide, from management key)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS openrouter_daily_requests (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            request_date DATE NOT NULL,
                            request_count INTEGER NOT NULL DEFAULT 0,
                            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            UNIQUE (user_id, request_date)
                        );
                        CREATE INDEX IF NOT EXISTS idx_openrouter_daily_requests_user_date
                            ON openrouter_daily_requests (user_id, request_date);
                    """)
                    
                    # Per-key daily breakdown for audit
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS openrouter_key_usage (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            key_label TEXT NOT NULL,
                            key_hash TEXT NOT NULL,
                            request_date DATE NOT NULL,
                            usage_daily INTEGER NOT NULL DEFAULT 0,
                            usage_weekly INTEGER NOT NULL DEFAULT 0,
                            usage_monthly INTEGER NOT NULL DEFAULT 0,
                            recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            UNIQUE (user_id, key_hash, request_date)
                        );
                        CREATE INDEX IF NOT EXISTS idx_openrouter_key_usage_user_date
                            ON openrouter_key_usage (user_id, request_date);
                    """)
                    
                    # Request log for audit
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS openrouter_request_log (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            model TEXT,
                            request_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            cost_usd NUMERIC(10,6) DEFAULT 0,
                            tokens_in INTEGER DEFAULT 0,
                            tokens_out INTEGER DEFAULT 0
                        );
                        CREATE INDEX IF NOT EXISTS idx_openrouter_request_log_user_ts
                            ON openrouter_request_log (user_id, request_ts);
                    """)
            logger.info("OpenRouterTracker: Neon tables initialized")
        except Exception as exc:
            logger.error(f"OpenRouterTracker: DB init failed: {exc}")
            raise
    
    def _fetch_keys_usage(self) -> List[Dict[str, Any]]:
        """Fetch per-key usage from OpenRouter using management key."""
        if not self.management_key:
            logger.warning("No management key configured; cannot fetch keys usage")
            return []
        
        try:
            resp = requests.get(
                f"{self.base_url}/keys",
                headers={"Authorization": f"Bearer {self.management_key}"},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except Exception as exc:
            logger.error(f"OpenRouterTracker: fetch_keys_usage failed: {exc}")
            return []
    
    def _fetch_credits(self) -> Dict[str, float]:
        """Fetch dollar credits from OpenRouter."""
        if not self.api_key:
            return {"total_credits": 10.0, "total_usage": 0.0, "remaining": 10.0}
        
        try:
            resp = requests.get(
                f"{self.base_url}/credits",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            total_credits = float(data.get("total_credits", 10.0))
            total_usage = float(data.get("total_usage", 0.0))
            return {
                "total_credits": total_credits,
                "total_usage": total_usage,
                "remaining": total_credits - total_usage
            }
        except Exception as exc:
            logger.error(f"OpenRouterTracker: fetch_credits failed: {exc}")
            return {"total_credits": 10.0, "total_usage": 0.0, "remaining": 10.0}
    
    def sync_org_usage(self) -> Dict[str, Any]:
        """
        Sync org-wide usage from OpenRouter:
        - Aggregate usage_daily across all keys for today's total requests
        - Fetch dollar credits
        - Record both to Neon
        """
        if not self.neon_url:
            return {"error": "No DB configured"}
        
        today = date.today()
        now = datetime.now(timezone.utc)
        
        # 1. Aggregate daily requests from all keys
        keys = self._fetch_keys_usage()
        total_daily_requests = sum(k.get("usage_daily", 0) for k in keys)
        total_weekly_requests = sum(k.get("usage_weekly", 0) for k in keys)
        total_monthly_requests = sum(k.get("usage_monthly", 0) for k in keys)
        
        # 2. Fetch dollar credits
        credits = self._fetch_credits()
        
        # 3. Record to Neon
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    # Upsert aggregated daily request count
                    cur.execute("""
                        INSERT INTO openrouter_daily_requests (user_id, request_date, request_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, request_date) 
                        DO UPDATE SET request_count = EXCLUDED.request_count,
                                      recorded_at = NOW()
                        RETURNING request_count;
                    """, (self.user_id, today, total_daily_requests))
                    
                    # Record per-key breakdown
                    for key in keys:
                        key_hash = key.get("hash", "")[:32]
                        key_label = key.get("name", key.get("label", "unknown"))
                        cur.execute("""
                            INSERT INTO openrouter_key_usage (user_id, key_label, key_hash, request_date, usage_daily, usage_weekly, usage_monthly)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (user_id, key_hash, request_date) 
                            DO UPDATE SET usage_daily = EXCLUDED.usage_daily,
                                          usage_weekly = EXCLUDED.usage_weekly,
                                          usage_monthly = EXCLUDED.usage_monthly,
                                          recorded_at = NOW()
                        """, (
                            self.user_id, key_label, key_hash, today,
                            key.get("usage_daily", 0),
                            key.get("usage_weekly", 0),
                            key.get("usage_monthly", 0)
                        ))
                    
                    # Record dollar spend
                    cur.execute("""
                        INSERT INTO openrouter_dollar_spend (user_id, total_credits, total_usage, remaining_credits)
                        VALUES (%s, %s, %s, %s)
                    """, (self.user_id, credits["total_credits"], credits["total_usage"], credits["remaining"]))
            
            logger.info(f"OpenRouterTracker: Synced org usage - {total_daily_requests} daily requests, ${credits['total_usage']:.4f} / ${credits['total_credits']:.2f}")
            
            return {
                "synced": True,
                "daily_requests": total_daily_requests,
                "weekly_requests": total_weekly_requests,
                "monthly_requests": total_monthly_requests,
                "dollar_credits": credits["total_credits"],
                "dollar_usage": credits["total_usage"],
                "dollar_remaining": credits["remaining"]
            }
        except Exception as exc:
            logger.error(f"OpenRouterTracker: sync_org_usage failed: {exc}")
            return {"synced": False, "error": str(exc)}
    
    def get_daily_status(self) -> Dict[str, Any]:
        """Get current daily request count and dollar spend from Neon."""
        if not self.neon_url:
            return {"error": "No DB configured"}
        
        today = date.today()
        
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Today's aggregated requests
                    cur.execute("""
                        SELECT request_count FROM openrouter_daily_requests
                        WHERE user_id = %s AND request_date = %s
                    """, (self.user_id, today))
                    row = cur.fetchone()
                    daily_requests = row["request_count"] if row else 0
                    
                    # Latest dollar spend
                    cur.execute("""
                        SELECT total_credits, total_usage, remaining_credits, recorded_at
                        FROM openrouter_dollar_spend
                        WHERE user_id = %s
                        ORDER BY recorded_at DESC
                        LIMIT 1
                    """, (self.user_id,))
                    dollar_row = cur.fetchone()
                    
                    return {
                        "requests": {
                            "daily_used": daily_requests,
                            "daily_limit": 1000,
                            "daily_remaining": max(0, 1000 - daily_requests),
                            "envelope_status": "deny" if daily_requests >= 1000 else "allow"
                        },
                        "dollars": {
                            "total_credits": float(dollar_row["total_credits"]) if dollar_row else 10.0,
                            "total_usage": float(dollar_row["total_usage"]) if dollar_row else 0.0,
                            "remaining": float(dollar_row["remaining_credits"]) if dollar_row else 10.0,
                            "last_synced": dollar_row["recorded_at"].isoformat() if dollar_row else None
                        }
                    }
        except Exception as exc:
            logger.error(f"OpenRouterTracker: get_daily_status failed: {exc}")
            return {"error": str(exc)}
    
    def get_narrator_summary(self) -> Dict[str, Any]:
        """Summary for narrator context embedding."""
        status = self.get_daily_status()
        if "error" in status:
            return {"openrouter_tracking": {"error": status["error"]}}
        
        req = status["requests"]
        dol = status["dollars"]
        
        summary = {
            "openrouter_tracking": {
                "daily_requests_used": req["daily_used"],
                "daily_requests_limit": req["daily_limit"],
                "daily_requests_remaining": req["daily_remaining"],
                "dollar_credits_total": dol["total_credits"],
                "dollar_usage": dol["total_usage"],
                "dollar_remaining": dol["remaining"],
                "last_synced": dol["last_synced"],
                "needs_action": req["daily_remaining"] < 100 or dol["remaining"] < 1.0
            }
        }
        
        if req["daily_remaining"] < 100:
            summary["openrouter_tracking"]["urgent_reminder"] = f"⚠️ OpenRouter free tier: {req['daily_remaining']} requests left today"
        if dol["remaining"] < 1.0:
            summary["openrouter_tracking"]["urgent_reminder"] = f"💰 OpenRouter credits: ${dol['remaining']:.2f} remaining"
            
        return summary


_global_tracker = None

def get_openrouter_tracker() -> OpenRouterTracker:
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = OpenRouterTracker()
    return _global_tracker

def sync_openrouter_org_usage() -> Dict[str, Any]:
    """MCP tool: Sync org-wide usage from OpenRouter (management key required)."""
    return get_openrouter_tracker().sync_org_usage()

def get_openrouter_status() -> Dict[str, Any]:
    """MCP tool: Get current daily request count and dollar spend."""
    return get_openrouter_tracker().get_daily_status()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tracker = OpenRouterTracker()
    print("=== Sync Org Usage ===")
    import json
    print(json.dumps(tracker.sync_org_usage(), indent=2, default=str))
    print("\n=== Daily Status ===")
    print(json.dumps(tracker.get_daily_status(), indent=2, default=str))
    print("\n=== Narrator Summary ===")
    print(json.dumps(tracker.get_narrator_summary(), indent=2, default=str))