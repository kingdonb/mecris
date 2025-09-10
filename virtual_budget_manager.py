"""
Virtual Budget Manager - Multi-provider LLM cost management

This system creates a virtual budget layer above all LLM providers,
managing spending allocation regardless of their billing models.
"""

import sqlite3
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import os

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
    def __init__(self, db_path: str = "mecris_virtual_budget.db"):
        self.db_path = db_path
        
        # Budget configuration - must be set before init_database()
        self.daily_budget = float(os.getenv('DAILY_BUDGET', '2.00'))
        self.monthly_budget = float(os.getenv('MONTHLY_BUDGET', '60.00'))
        self.emergency_reserve_ratio = 0.20  # 20% held back for emergencies
        
        self.init_database()
        
        # Provider-specific pricing
        self.pricing = {
            Provider.ANTHROPIC: {
                "claude-3-5-sonnet-20241022": {
                    "input": 3.0 / 1_000_000,   # $3 per million input tokens
                    "output": 15.0 / 1_000_000  # $15 per million output tokens
                },
                "claude-3-5-haiku-20241022": {
                    "input": 0.25 / 1_000_000,  # $0.25 per million input tokens  
                    "output": 1.25 / 1_000_000  # $1.25 per million output tokens
                }
            },
            Provider.GROQ: {
                "openai/gpt-oss-20b": {
                    "input": 0.10 / 1_000_000,   # $0.10 per million tokens
                    "output": 0.10 / 1_000_000   # Same for input/output
                },
                "openai/gpt-oss-120b": {
                    "input": 0.15 / 1_000_000,   # $0.15 per million tokens
                    "output": 0.15 / 1_000_000   # Same for input/output
                },
                "llama-3.1-8b-instant": {
                    "input": 0.05 / 1_000_000,   # Estimated pricing
                    "output": 0.05 / 1_000_000
                },
                "llama-3.3-70b-versatile": {
                    "input": 0.08 / 1_000_000,   # Estimated pricing
                    "output": 0.08 / 1_000_000
                }
            }
        }
        
        
    def init_database(self):
        """Initialize database schema for virtual budget system."""
        with sqlite3.connect(self.db_path) as conn:
            # Virtual budget allocations
            conn.execute("""
                CREATE TABLE IF NOT EXISTS budget_allocations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_type TEXT NOT NULL,
                    budget_amount REAL NOT NULL,
                    remaining_amount REAL NOT NULL,
                    period_start DATE NOT NULL,
                    period_end DATE NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Multi-provider usage tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS provider_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    estimated_cost REAL NOT NULL,
                    actual_cost REAL DEFAULT NULL,
                    timestamp TEXT NOT NULL,
                    session_type TEXT DEFAULT 'interactive',
                    notes TEXT DEFAULT '',
                    reconciled BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Reconciliation jobs tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    job_date DATE NOT NULL,
                    estimated_total REAL NOT NULL,
                    actual_total REAL NOT NULL,
                    drift_percentage REAL NOT NULL,
                    records_reconciled INTEGER NOT NULL,
                    reconciled_at TEXT NOT NULL
                )
            """)
            
            # Provider cache for scraped/API data
            conn.execute("""
                CREATE TABLE IF NOT EXISTS provider_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    cache_data TEXT NOT NULL,
                    cached_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    UNIQUE(provider, cache_key)
                )
            """)
            
            # Initialize daily budget if needed
            self._ensure_daily_budget()
    
    def _ensure_daily_budget(self):
        """Ensure today's budget allocation exists."""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id FROM budget_allocations 
                WHERE period_type = 'daily' AND period_start = ?
            """, (today.isoformat(),))
            
            if not cursor.fetchone():
                # Create today's budget
                conn.execute("""
                    INSERT INTO budget_allocations 
                    (period_type, budget_amount, remaining_amount, period_start, period_end, created_at, updated_at)
                    VALUES ('daily', ?, ?, ?, ?, ?, ?)
                """, (
                    self.daily_budget,
                    self.daily_budget,
                    today.isoformat(),
                    tomorrow.isoformat(),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
    
    def calculate_cost(self, provider: Provider, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost for a request."""
        if provider not in self.pricing or model not in self.pricing[provider]:
            # Default to most expensive model for safety
            if provider == Provider.ANTHROPIC:
                pricing = self.pricing[Provider.ANTHROPIC]["claude-3-5-sonnet-20241022"]
            else:
                pricing = self.pricing[Provider.GROQ]["openai/gpt-oss-120b"]
        else:
            pricing = self.pricing[provider][model]
        
        input_cost = input_tokens * pricing["input"]
        output_cost = output_tokens * pricing["output"]
        return round(input_cost + output_cost, 6)  # 6 decimal places for precision
    
    def can_afford(self, cost: float, include_reserve: bool = True) -> Dict:
        """Check if we can afford a request within budget constraints."""
        self._ensure_daily_budget()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT remaining_amount FROM budget_allocations 
                WHERE period_type = 'daily' AND period_start = ?
            """, (date.today().isoformat(),))
            
            result = cursor.fetchone()
            if not result:
                return {"can_afford": False, "reason": "No daily budget found"}
            
            remaining = result[0]
            available = remaining * (1 - self.emergency_reserve_ratio) if include_reserve else remaining
            
            if cost <= available:
                return {
                    "can_afford": True,
                    "remaining": remaining,
                    "available": available,
                    "cost": cost,
                    "after_spending": remaining - cost
                }
            else:
                return {
                    "can_afford": False,
                    "reason": "Insufficient budget",
                    "remaining": remaining,
                    "available": available,
                    "cost": cost,
                    "shortfall": cost - available
                }
    
    def record_usage(self, provider: Provider, model: str, input_tokens: int, output_tokens: int,
                    session_type: str = "interactive", notes: str = "", emergency_override: bool = False) -> Dict:
        """Record usage and deduct from virtual budget."""
        cost = self.calculate_cost(provider, model, input_tokens, output_tokens)
        timestamp = datetime.now().isoformat()
        
        # Check if we can afford this
        affordability = self.can_afford(cost, include_reserve=not emergency_override)
        
        if not affordability["can_afford"] and not emergency_override:
            return {
                "recorded": False,
                "reason": affordability["reason"],
                "cost": cost,
                "affordability": affordability
            }
        
        # Record the usage
        with sqlite3.connect(self.db_path) as conn:
            # Insert usage record
            conn.execute("""
                INSERT INTO provider_usage 
                (provider, model, input_tokens, output_tokens, estimated_cost, timestamp, session_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (provider.value, model, input_tokens, output_tokens, cost, timestamp, session_type, notes))
            
            # Deduct from daily budget
            conn.execute("""
                UPDATE budget_allocations 
                SET remaining_amount = remaining_amount - ?, updated_at = ?
                WHERE period_type = 'daily' AND period_start = ?
            """, (cost, timestamp, date.today().isoformat()))
            
        return {
            "recorded": True,
            "cost": cost,
            "provider": provider.value,
            "model": model,
            "emergency_override": emergency_override,
            "remaining_budget": affordability.get("after_spending", 0)
        }
    
    def get_budget_status(self) -> Dict:
        """Get comprehensive budget status across all providers."""
        self._ensure_daily_budget()
        
        with sqlite3.connect(self.db_path) as conn:
            # Today's budget
            cursor = conn.execute("""
                SELECT budget_amount, remaining_amount, updated_at FROM budget_allocations 
                WHERE period_type = 'daily' AND period_start = ?
            """, (date.today().isoformat(),))
            
            daily_budget = cursor.fetchone()
            
            # Today's usage by provider
            cursor = conn.execute("""
                SELECT provider, SUM(estimated_cost), COUNT(*) FROM provider_usage 
                WHERE DATE(timestamp) = DATE('now')
                GROUP BY provider
            """)
            
            provider_usage = {row[0]: {"cost": row[1], "sessions": row[2]} for row in cursor.fetchall()}
            
            # Recent reconciliation accuracy
            cursor = conn.execute("""
                SELECT provider, AVG(ABS(drift_percentage)) FROM reconciliation_jobs 
                WHERE job_date > DATE('now', '-7 days')
                GROUP BY provider
            """)
            
            reconciliation_accuracy = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Build comprehensive status
            if not daily_budget:
                return {"error": "No daily budget allocation found"}
            
            budget_amount, remaining, last_updated = daily_budget
            spent_today = budget_amount - remaining
            available_spending = remaining * (1 - self.emergency_reserve_ratio)
            
            # Generate alerts
            alerts = []
            if remaining < (budget_amount * 0.2):
                alerts.append("LOW_DAILY_BUDGET")
            if spent_today > (budget_amount * 0.8):
                alerts.append("HIGH_DAILY_SPEND")
            if available_spending < 0.50:
                alerts.append("NEARING_RESERVE")
            
            return {
                "daily_budget": {
                    "allocated": budget_amount,
                    "remaining": remaining,
                    "spent": spent_today,
                    "available": available_spending,
                    "emergency_reserve": remaining - available_spending
                },
                "provider_breakdown": provider_usage,
                "reconciliation_accuracy": reconciliation_accuracy,
                "alerts": alerts,
                "budget_health": "GOOD" if len(alerts) == 0 else "WARNING" if len(alerts) < 2 else "CRITICAL",
                "last_updated": last_updated
            }
    
    def reset_daily_budget(self) -> Dict:
        """Reset daily budget (called by daily cron job)."""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Create tomorrow's budget
            conn.execute("""
                INSERT OR REPLACE INTO budget_allocations 
                (period_type, budget_amount, remaining_amount, period_start, period_end, created_at, updated_at)
                VALUES ('daily', ?, ?, ?, ?, ?, ?)
            """, (
                self.daily_budget,
                self.daily_budget,
                today.isoformat(),
                tomorrow.isoformat(),
                timestamp,
                timestamp
            ))
        
        return {
            "reset": True,
            "new_budget": self.daily_budget,
            "date": today.isoformat(),
            "timestamp": timestamp
        }
    
    def get_usage_summary(self, days: int = 7) -> Dict:
        """Get comprehensive usage summary across providers."""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Total usage by provider
            cursor = conn.execute("""
                SELECT 
                    provider,
                    COUNT(*) as sessions,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(estimated_cost) as estimated_cost,
                    SUM(CASE WHEN reconciled THEN actual_cost ELSE estimated_cost END) as total_cost
                FROM provider_usage 
                WHERE timestamp > ?
                GROUP BY provider
            """, (cutoff_date,))
            
            provider_totals = {
                row[0]: {
                    "sessions": row[1],
                    "input_tokens": row[2],
                    "output_tokens": row[3],
                    "estimated_cost": row[4],
                    "total_cost": row[5]
                }
                for row in cursor.fetchall()
            }
            
            # Daily breakdown
            cursor = conn.execute("""
                SELECT 
                    DATE(timestamp) as date,
                    provider,
                    SUM(estimated_cost) as daily_cost
                FROM provider_usage 
                WHERE timestamp > ?
                GROUP BY DATE(timestamp), provider
                ORDER BY date DESC
            """, (cutoff_date,))
            
            daily_breakdown = {}
            for row in cursor.fetchall():
                date_key, provider, cost = row
                if date_key not in daily_breakdown:
                    daily_breakdown[date_key] = {}
                daily_breakdown[date_key][provider] = cost
        
        return {
            "period_days": days,
            "provider_totals": provider_totals,
            "daily_breakdown": daily_breakdown,
            "total_estimated": sum(p["estimated_cost"] for p in provider_totals.values()),
            "total_actual": sum(p["total_cost"] for p in provider_totals.values())
        }

# Convenience functions for backward compatibility
def record_anthropic_usage(model: str, input_tokens: int, output_tokens: int, session_type: str = "interactive", notes: str = "") -> float:
    """Record Anthropic usage session."""
    manager = VirtualBudgetManager()
    result = manager.record_usage(Provider.ANTHROPIC, model, input_tokens, output_tokens, session_type, notes)
    return result.get("cost", 0.0) if result.get("recorded", False) else 0.0

def record_groq_usage(model: str, input_tokens: int, output_tokens: int, session_type: str = "interactive", notes: str = "") -> float:
    """Record Groq usage session."""
    manager = VirtualBudgetManager()
    result = manager.record_usage(Provider.GROQ, model, input_tokens, output_tokens, session_type, notes)
    return result.get("cost", 0.0) if result.get("recorded", False) else 0.0

def get_virtual_budget_status() -> Dict:
    """Get current virtual budget status."""
    manager = VirtualBudgetManager()
    return manager.get_budget_status()

if __name__ == "__main__":
    # Test the virtual budget system
    manager = VirtualBudgetManager()
    
    print("=== Virtual Budget Manager Test ===")
    
    # Test Anthropic usage
    anthro_result = manager.record_usage(
        Provider.ANTHROPIC, 
        "claude-3-5-sonnet-20241022", 
        1000, 500, 
        "test", 
        "Testing Anthropic integration"
    )
    print(f"Anthropic test: {anthro_result}")
    
    # Test Groq usage
    groq_result = manager.record_usage(
        Provider.GROQ,
        "openai/gpt-oss-20b",
        2000, 800,
        "test",
        "Testing Groq integration"
    )
    print(f"Groq test: {groq_result}")
    
    # Get budget status
    status = manager.get_budget_status()
    print(f"Budget status: {json.dumps(status, indent=2)}")
    
    # Get usage summary
    summary = manager.get_usage_summary(7)
    print(f"Usage summary: {json.dumps(summary, indent=2)}")