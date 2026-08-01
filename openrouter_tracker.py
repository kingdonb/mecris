#!/usr/bin/env python3
"""
OpenRouter Usage Tracker

Tracks both:
1. Daily request count (1000 free requests/day, resets midnight UTC) - via local envelope
2. Dollar spend ($10 credit limit) - via OpenRouter API /api/v1/credits

Periodically polls OpenRouter for dollar usage and records to Neon.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("mecris.openrouter_tracker")

class OpenRouterTracker:
    def __init__(self, neon_url: Optional[str] = None, user_id: Optional[str] = None, api_key: Optional[str] = None):
        self.neon_url = neon_url or os.getenv("NEON_DB_URL")
        self.user_id = user_id or os.getenv("DEFAULT_USER_ID", "yebyen")
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("PET_GROQ_API_KEY")  # check both
        
        if not self.neon_url:
            logger.warning("NEON_DB_URL not set; OpenRouterTracker will fail on DB operations.")
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
                    # Dollar spend tracking (synced from OpenRouter)
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
                    
                    # Daily request count (local tracking for 1000 free req/day)
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
    
    def record_request(self, model: str = "", cost_usd: float = 0.0, tokens_in: int = 0, tokens_out: int = 0) -> Dict[str, Any]:
        """
        Record an OpenRouter API request locally.
        Returns current daily count and envelope status.
        """
        if not self.neon_url:
            return {"error": "No DB configured"}
            
        today = datetime.now(timezone.utc).date()
        now = datetime.now(timezone.utc)
        
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    # Upsert daily request count
                    cur.execute("""
                        INSERT INTO openrouter_daily_requests (user_id, request_date, request_count)
                        VALUES (%s, %s, 1)
                        ON CONFLICT (user_id, request_date) 
                        DO UPDATE SET request_count = openrouter_daily_requests.request_count + 1,
                                      recorded_at = NOW()
                        RETURNING request_count;
                    """, (self.user_id, today))
                    
                    daily_count = cur.fetchone()[0]
                    
                    # Log request details
                    cur.execute("""
                        INSERT INTO openrouter_request_log (user_id, model, request_ts, cost_usd, tokens_in, tokens_out)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (self.user_id, model, now, cost_usd, tokens_in, tokens_out))
                    
                    return {
                        "recorded": True,
                        "daily_request_count": daily_count,
                        "limit": 1000,
                        "remaining": max(0, 1000 - daily_count),
                        "envelope_status": "deny" if daily_count >= 1000 else "allow"
                    }
        except Exception as exc:
            logger.error(f"OpenRouterTracker: record_request failed: {exc}")
            return {"recorded": False, "error": str(exc)}
    
    def get_daily_status(self) -> Dict[str, Any]:
        """Get current daily request count and dollar spend."""
        if not self.neon_url:
            return {"error": "No DB configured"}
        
        today = datetime.now(timezone.utc).date()
        
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Today's requests
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
    
    def sync_dollar_usage(self) -> Dict[str, Any]:
        """
        Poll OpenRouter /api/v1/credits and record to Neon.
        Returns the synced values.
        """
        if not self.api_key:
            return {"error": "No API key configured"}
        if not self.neon_url:
            return {"error": "No DB configured"}
        
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
            remaining = total_credits - total_usage
            
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO openrouter_dollar_spend (user_id, total_credits, total_usage, remaining_credits)
                        VALUES (%s, %s, %s, %s)
                    """, (self.user_id, total_credits, total_usage, remaining))
            
            logger.info(f"OpenRouterTracker: Synced dollar usage - ${total_usage:.4f} / ${total_credits:.2f}")
            return {
                "synced": True,
                "total_credits": total_credits,
                "total_usage": total_usage,
                "remaining": remaining
            }
        except Exception as exc:
            logger.error(f"OpenRouterTracker: sync_dollar_usage failed: {exc}")
            return {"synced": False, "error": str(exc)}
    
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

def record_openrouter_request(model: str = "", cost_usd: float = 0.0, tokens_in: int = 0, tokens_out: int = 0) -> Dict[str, Any]:
    return get_openrouter_tracker().record_request(model, cost_usd, tokens_in, tokens_out)

def get_openrouter_status() -> Dict[str, Any]:
    return get_openrouter_tracker().get_daily_status()

def sync_openrouter_dollars() -> Dict[str, Any]:
    return get_openrouter_tracker().sync_dollar_usage()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tracker = OpenRouterTracker()
    print("=== Daily Status ===")
    import json
    print(json.dumps(tracker.get_daily_status(), indent=2, default=str))
    print("\n=== Sync Dollar Usage ===")
    print(json.dumps(tracker.sync_dollar_usage(), indent=2))
    print("\n=== Narrator Summary ===")
    print(json.dumps(tracker.get_narrator_summary(), indent=2, default=str))