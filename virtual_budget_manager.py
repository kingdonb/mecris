"""
Virtual Budget Manager - Multi-provider LLM cost management

This system creates a virtual budget layer above all LLM providers,
managing spending allocation regardless of their billing models.
"""

import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

from services.credentials_manager import credentials_manager

logger = logging.getLogger("mecris.virtual_budget")

class Provider(Enum):
    ANTHROPIC = "anthropic"
    GROQ = "groq"

@dataclass
class ProviderUsage:
    provider: Provider
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    actual_cost: Optional[float] = None
    timestamp: str = None
    reconciled: bool = False

class VirtualBudgetManager:
    def __init__(self, user_id: str = None):
        self.neon_url = os.getenv("NEON_DB_URL")
        self.user_id = credentials_manager.resolve_user_id(user_id)
        if not self.neon_url:
            logger.warning("NEON_DB_URL not set in VirtualBudgetManager. Budgeting will fail.")
            
        # Budget configuration
        self.daily_budget = float(os.getenv("DAILY_BUDGET", "2.00"))
        self.monthly_budget = float(os.getenv("MONTHLY_BUDGET", "60.00"))
        self.emergency_reserve_ratio = 0.20
        
        # Provider-specific pricing
        self.pricing = {
            Provider.ANTHROPIC: {
                "claude-3-5-sonnet-20241022": {
                    "input": 3.0 / 1_000_000,
                    "output": 15.0 / 1_000_000
                },
                "claude-3-5-haiku-20241022": {
                    "input": 0.25 / 1_000_000,
                    "output": 1.25 / 1_000_000
                }
            },
            Provider.GROQ: {
                "openai/gpt-oss-20b": {"input": 0.10 / 1_000_000, "output": 0.10 / 1_000_000},
                "openai/gpt-oss-120b": {"input": 0.15 / 1_000_000, "output": 0.15 / 1_000_000},
                "llama-3.1-8b-instant": {"input": 0.05 / 1_000_000, "output": 0.05 / 1_000_000},
                "llama-3.3-70b-versatile": {"input": 0.08 / 1_000_000, "output": 0.08 / 1_000_000}
            }
        }
        
        if self.neon_url:
            self.init_database()

    def init_database(self):
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS budget_allocations (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT REFERENCES users(pocket_id_sub),
                            period_type TEXT NOT NULL,
                            budget_amount DOUBLE PRECISION NOT NULL,
                            remaining_amount DOUBLE PRECISION NOT NULL,
                            period_start DATE NOT NULL,
                            period_end DATE NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL,
                            UNIQUE(user_id, period_type, period_start)
                        );
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS provider_usage (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT REFERENCES users(pocket_id_sub),
                            provider TEXT NOT NULL,
                            model TEXT NOT NULL,
                            input_tokens INTEGER NOT NULL,
                            output_tokens INTEGER NOT NULL,
                            estimated_cost DOUBLE PRECISION NOT NULL,
                            actual_cost DOUBLE PRECISION DEFAULT NULL,
                            timestamp TIMESTAMPTZ NOT NULL,
                            session_type TEXT DEFAULT 'interactive',
                            notes TEXT DEFAULT '',
                            reconciled BOOLEAN DEFAULT FALSE
                        );
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS reconciliation_jobs (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT REFERENCES users(pocket_id_sub),
                            provider TEXT NOT NULL,
                            job_date DATE NOT NULL,
                            estimated_total DOUBLE PRECISION NOT NULL,
                            actual_total DOUBLE PRECISION NOT NULL,
                            drift_percentage DOUBLE PRECISION NOT NULL,
                            records_reconciled INTEGER NOT NULL,
                            reconciled_at TIMESTAMPTZ NOT NULL
                        );
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS provider_cache (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT REFERENCES users(pocket_id_sub),
                            provider TEXT NOT NULL,
                            cache_key TEXT NOT NULL,
                            cache_data TEXT NOT NULL,
                            cached_at TIMESTAMPTZ NOT NULL,
                            expires_at TIMESTAMPTZ NOT NULL,
                            UNIQUE(user_id, provider, cache_key)
                        );
                    """)
            self._ensure_daily_budget(self.user_id)
        except Exception as e:
            logger.error(f"Neon DB init failed: {e}")

    def _ensure_daily_budget(self, user_id: str = None):
        target_user_id = user_id or self.user_id
        if not self.neon_url or not target_user_id: return
        today = date.today()
        tomorrow = today + timedelta(days=1)
        now = datetime.now()
        
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM budget_allocations WHERE user_id = %s AND period_type = %s AND period_start = %s", (target_user_id, "daily", today))
                    if not cur.fetchone():
                        cur.execute("""
                            INSERT INTO budget_allocations 
                            (user_id, period_type, budget_amount, remaining_amount, period_start, period_end, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (target_user_id, "daily", self.daily_budget, self.daily_budget, today, tomorrow, now, now))
        except Exception as e:
            logger.error(f"ensure_daily_budget failed: {e}")

    def calculate_cost(self, provider: Provider, model: str, input_tokens: int, output_tokens: int) -> float:
        if provider not in self.pricing or model not in self.pricing[provider]:
            pricing = self.pricing[Provider.ANTHROPIC]["claude-3-5-sonnet-20241022"] if provider == Provider.ANTHROPIC else self.pricing[Provider.GROQ]["openai/gpt-oss-120b"]
        else:
            pricing = self.pricing[provider][model]
        return round(input_tokens * pricing["input"] + output_tokens * pricing["output"], 6)

    def can_afford(self, cost: float, include_reserve: bool = True, user_id: str = None) -> Dict:
        target_user_id = user_id or self.user_id
        if not self.neon_url: return {"can_afford": False, "reason": "No DB"}
        self._ensure_daily_budget(target_user_id)
        today = date.today()
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT remaining_amount FROM budget_allocations WHERE user_id = %s AND period_type = %s AND period_start = %s", (target_user_id, "daily", today))
                    res = cur.fetchone()
                    if res:
                        rem = res[0]
                        if rem <= 0:
                            return {"can_afford": False, "reason": "BUDGET_EXHAUSTED", "remaining": rem, "available": 0, "cost": cost}
                        
                        avail = rem * (1 - self.emergency_reserve_ratio) if include_reserve else rem
                        if cost <= avail: return {"can_afford": True, "remaining": rem, "available": avail, "cost": cost, "after_spending": rem - cost}
                        return {"can_afford": False, "reason": "Insufficient budget", "remaining": rem, "available": avail, "cost": cost, "shortfall": cost - avail}
        except Exception as e:
            logger.error(f"can_afford check failed for {target_user_id}: {e}")
        return {"can_afford": False, "reason": "DB Error"}

    def record_usage(self, provider: Provider, model: str, input_tokens: int, output_tokens: int, session_type: str = "interactive", notes: str = "", emergency_override: bool = False, user_id: str = None) -> Dict:
        target_user_id = user_id or self.user_id
        cost = self.calculate_cost(provider, model, input_tokens, output_tokens)
        afford = self.can_afford(cost, include_reserve=not emergency_override, user_id=target_user_id)
        if not afford["can_afford"] and not emergency_override:
            return {"recorded": False, "reason": afford.get("reason", "Unknown"), "cost": cost, "affordability": afford}
        now, today = datetime.now(), date.today()
        
        if not self.neon_url:
            return {"recorded": False, "reason": "No DB configured"}
            
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO provider_usage (user_id, provider, model, input_tokens, output_tokens, estimated_cost, timestamp, session_type, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (target_user_id, provider.value, model, input_tokens, output_tokens, cost, now, session_type, notes))
                    cur.execute("UPDATE budget_allocations SET remaining_amount = remaining_amount - %s, updated_at = %s WHERE user_id = %s AND period_type = %s AND period_start = %s", (cost, now, target_user_id, "daily", today))
            return {"recorded": True, "cost": cost, "provider": provider.value, "model": model, "emergency_override": emergency_override, "remaining_budget": afford.get("after_spending", 0)}
        except Exception as e:
            logger.error(f"record_usage failed for {target_user_id}: {e}")
            return {"recorded": False, "reason": str(e)}

    def get_budget_status(self, user_id: str = None) -> Dict:
        target_user_id = user_id or self.user_id
        if not self.neon_url: return {"error": "Neon DB not configured"}
        self._ensure_daily_budget(target_user_id)
        today = date.today()
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT budget_amount, remaining_amount, updated_at FROM budget_allocations WHERE user_id = %s AND period_type = %s AND period_start = %s", (target_user_id, "daily", today))
                    dbudget = cur.fetchone()
                    cur.execute("SELECT provider, SUM(estimated_cost) as cost, COUNT(*) as sessions FROM provider_usage WHERE user_id = %s AND timestamp::date = %s GROUP BY provider", (target_user_id, today))
                    provider_rows = cur.fetchall()
                    provider_usage = {row['provider']: {'cost': row['cost'], 'sessions': row['sessions']} for row in provider_rows}
                    cur.execute("SELECT provider, AVG(ABS(drift_percentage)) as drift FROM reconciliation_jobs WHERE user_id = %s AND job_date > CURRENT_DATE - INTERVAL '7 days' GROUP BY provider", (target_user_id,))
                    recon_rows = cur.fetchall()
                    recon_acc = {row['provider']: row['drift'] for row in recon_rows}
                    if not dbudget: return {"error": f"No daily budget found for {target_user_id} in Neon"}
                    b_amt, rem, updated = dbudget["budget_amount"], dbudget["remaining_amount"], str(dbudget["updated_at"])
                    spent, avail = b_amt - rem, rem * (1 - self.emergency_reserve_ratio)
                    alerts = []
                    if rem <= 0: alerts.append("BUDGET_EXHAUSTED")
                    if 0 < rem < (b_amt * 0.2): alerts.append("LOW_DAILY_BUDGET")
                    if spent > (b_amt * 0.8): alerts.append("HIGH_DAILY_SPEND")
                    if avail < 0.50 and rem > 0: alerts.append("NEARING_RESERVE")
                    
                    return {
                        "daily_budget": {"allocated": b_amt, "remaining": rem, "spent": spent, "available": max(0, avail), "emergency_reserve": max(0, rem - avail)}, 
                        "provider_breakdown": provider_usage, 
                        "reconciliation_accuracy": recon_acc, 
                        "alerts": alerts, 
                        "budget_health": "GOOD" if not alerts else "WARNING" if "BUDGET_EXHAUSTED" not in alerts else "CRITICAL", 
                        "is_halted": rem <= 0,
                        "last_updated": updated
                    }
        except Exception as e:
            logger.error(f"get_budget_status failed: {e}")
            return {"error": str(e)}

    def reset_daily_budget(self, user_id: str = None) -> Dict:
        target_user_id = user_id or self.user_id
        if not self.neon_url: return {"error": "Neon DB not configured"}
        today, now = date.today(), datetime.now()
        tomorrow = today + timedelta(days=1)
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO budget_allocations (user_id, period_type, budget_amount, remaining_amount, period_start, period_end, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", (target_user_id, "daily", self.daily_budget, self.daily_budget, today, tomorrow, now, now))
            return {"reset": True, "new_budget": self.daily_budget, "date": today.isoformat(), "timestamp": now.isoformat()}
        except Exception as e:
            logger.error(f"reset_daily_budget failed for {target_user_id}: {e}")
            return {"error": str(e)}

    def get_usage_summary(self, days: int = 7, user_id: str = None) -> Dict:
        target_user_id = user_id or self.user_id
        if not self.neon_url: return {"error": "Neon DB not configured"}
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        try:
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT provider, COUNT(*) as sessions, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens, SUM(estimated_cost) as estimated_cost, SUM(CASE WHEN reconciled THEN actual_cost ELSE estimated_cost END) as total_cost FROM provider_usage WHERE user_id = %s AND timestamp > %s GROUP BY provider", (target_user_id, cutoff,))
                    ptotals = {row["provider"]: dict(row) for row in cur.fetchall()}
                    cur.execute("SELECT timestamp::date as date, provider, SUM(estimated_cost) as daily_cost FROM provider_usage WHERE user_id = %s AND timestamp > %s GROUP BY timestamp::date, provider ORDER BY date DESC", (target_user_id, cutoff,))
                    breakdown = {}
                    for row in cur.fetchall():
                        d = str(row["date"])
                        if d not in breakdown: breakdown[d] = {}
                        breakdown[d][row["provider"]] = row["daily_cost"]
                    return {"period_days": days, "provider_totals": ptotals, "daily_breakdown": breakdown, "total_estimated": sum(p["estimated_cost"] for p in ptotals.values()), "total_actual": sum(p["total_cost"] for p in ptotals.values())}
        except Exception as e:
            logger.error(f"get_usage_summary failed for {target_user_id}: {e}")
            return {"error": str(e)}

def record_anthropic_usage(model: str, input_tokens: int, output_tokens: int, session_type: str = "interactive", notes: str = "", user_id: str = None) -> float:
    return VirtualBudgetManager(user_id=user_id).record_usage(Provider.ANTHROPIC, model, input_tokens, output_tokens, session_type, notes, user_id=user_id).get("cost", 0.0)

def record_groq_usage(model: str, input_tokens: int, output_tokens: int, session_type: str = "interactive", notes: str = "", user_id: str = None) -> float:
    return VirtualBudgetManager(user_id=user_id).record_usage(Provider.GROQ, model, input_tokens, output_tokens, session_type, notes, user_id=user_id).get("cost", 0.0)

def get_virtual_budget_status(user_id: str = None) -> Dict:
    return VirtualBudgetManager(user_id=user_id).get_budget_status(user_id=user_id)

if __name__ == "__main__":
    vbm = VirtualBudgetManager()
    print("=== VBM Status ===")
    print(json.dumps(vbm.get_budget_status(), indent=2))
