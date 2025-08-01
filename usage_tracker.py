"""
Local usage tracking for Claude API costs and budget management.
Since Anthropic doesn't provide programmatic credit balance API,
we maintain local estimates and allow manual budget updates.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import os

@dataclass
class UsageSession:
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    session_type: str  # 'interactive', 'ping', 'emergency'
    notes: str = ""

class UsageTracker:
    def __init__(self, db_path: str = "mecris_usage.db"):
        self.db_path = db_path
        self.init_database()
        
        # Current pricing (as of 2025) - Claude 3.5 Sonnet
        # Input: $3/million tokens, Output: $15/million tokens
        self.pricing = {
            "claude-3-5-sonnet-20241022": {
                "input": 3.0 / 1_000_000,   # $3 per million input tokens
                "output": 15.0 / 1_000_000  # $15 per million output tokens
            },
            "claude-3-5-haiku-20241022": {
                "input": 0.25 / 1_000_000,  # $0.25 per million input tokens  
                "output": 1.25 / 1_000_000  # $1.25 per million output tokens
            }
        }
    
    def init_database(self):
        """Initialize SQLite database for usage tracking."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    estimated_cost REAL NOT NULL,
                    session_type TEXT NOT NULL,
                    notes TEXT DEFAULT ''
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS budget_tracking (
                    id INTEGER PRIMARY KEY,
                    total_budget REAL NOT NULL,
                    remaining_budget REAL NOT NULL,
                    budget_period_start TEXT NOT NULL,
                    budget_period_end TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
            """)
            
            # Initialize budget if not exists
            cursor = conn.execute("SELECT COUNT(*) FROM budget_tracking")
            if cursor.fetchone()[0] == 0:
                # Default budget from your context: $18.21 remaining until Aug 5
                conn.execute("""
                    INSERT INTO budget_tracking 
                    (id, total_budget, remaining_budget, budget_period_start, budget_period_end, last_updated)
                    VALUES (1, 20.26, 18.21, '2025-08-01', '2025-08-05', ?)
                """, (datetime.now().isoformat(),))
    
    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost for a session."""
        if model not in self.pricing:
            # Default to Sonnet pricing if model not recognized
            model = "claude-3-5-sonnet-20241022"
        
        pricing = self.pricing[model]
        input_cost = input_tokens * pricing["input"]
        output_cost = output_tokens * pricing["output"]
        return round(input_cost + output_cost, 4)
    
    def record_session(self, model: str, input_tokens: int, output_tokens: int, 
                      session_type: str = "interactive", notes: str = "") -> float:
        """Record a usage session and return estimated cost."""
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO usage_sessions 
                (timestamp, model, input_tokens, output_tokens, estimated_cost, session_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, model, input_tokens, output_tokens, cost, session_type, notes))
            
            # Update remaining budget
            conn.execute("""
                UPDATE budget_tracking 
                SET remaining_budget = remaining_budget - ?, last_updated = ?
                WHERE id = 1
            """, (cost, timestamp))
        
        return cost
    
    def get_usage_summary(self, days: int = 7) -> Dict:
        """Get usage summary for the last N days."""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Total usage in period
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as session_count,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(estimated_cost) as total_cost
                FROM usage_sessions 
                WHERE timestamp > ?
            """, (cutoff_date,))
            
            totals = cursor.fetchone()
            
            # Usage by day
            cursor = conn.execute("""
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as sessions,
                    SUM(estimated_cost) as daily_cost
                FROM usage_sessions 
                WHERE timestamp > ?
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """, (cutoff_date,))
            
            daily_usage = cursor.fetchall()
            
            # Usage by session type
            cursor = conn.execute("""
                SELECT 
                    session_type,
                    COUNT(*) as sessions,
                    SUM(estimated_cost) as type_cost
                FROM usage_sessions 
                WHERE timestamp > ?
                GROUP BY session_type
            """, (cutoff_date,))
            
            by_type = cursor.fetchall()
            
            # Budget info
            cursor = conn.execute("SELECT * FROM budget_tracking WHERE id = 1")
            budget_info = cursor.fetchone()
        
        return {
            "period_days": days,
            "total_sessions": totals[0] or 0,
            "total_input_tokens": totals[1] or 0,
            "total_output_tokens": totals[2] or 0,
            "total_cost": round(totals[3] or 0, 4),
            "daily_usage": [
                {"date": row[0], "sessions": row[1], "cost": round(row[2], 4)}
                for row in daily_usage
            ],
            "usage_by_type": [
                {"type": row[0], "sessions": row[1], "cost": round(row[2], 4)}
                for row in by_type
            ],
            "budget": {
                "total": budget_info[1] if budget_info else 0,
                "remaining": budget_info[2] if budget_info else 0,
                "period_start": budget_info[3] if budget_info else None,
                "period_end": budget_info[4] if budget_info else None,
                "last_updated": budget_info[5] if budget_info else None
            } if budget_info else None
        }
    
    def update_budget(self, remaining_budget: float, total_budget: Optional[float] = None, 
                     period_end: Optional[str] = None) -> Dict:
        """Manually update budget information."""
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            if total_budget and period_end:
                # Full budget update
                conn.execute("""
                    UPDATE budget_tracking 
                    SET total_budget = ?, remaining_budget = ?, budget_period_end = ?, last_updated = ?
                    WHERE id = 1
                """, (total_budget, remaining_budget, period_end, timestamp))
            else:
                # Just update remaining budget
                conn.execute("""
                    UPDATE budget_tracking 
                    SET remaining_budget = ?, last_updated = ?
                    WHERE id = 1
                """, (remaining_budget, timestamp))
            
            # Get updated budget info
            cursor = conn.execute("SELECT * FROM budget_tracking WHERE id = 1")
            budget_info = cursor.fetchone()
        
        return {
            "total": budget_info[1],
            "remaining": budget_info[2],
            "period_start": budget_info[3],
            "period_end": budget_info[4],
            "last_updated": budget_info[5]
        }
    
    def get_budget_status(self) -> Dict:
        """Get current budget status with alerts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM budget_tracking WHERE id = 1")
            budget_info = cursor.fetchone()
            
            if not budget_info:
                return {"error": "No budget information found"}
            
            total, remaining = budget_info[1], budget_info[2]
            period_end = datetime.fromisoformat(budget_info[4])
            days_remaining = (period_end - datetime.now()).days
            
            # Calculate burn rate
            cursor = conn.execute("""
                SELECT SUM(estimated_cost) FROM usage_sessions 
                WHERE DATE(timestamp) = DATE('now')
            """)
            today_spend = cursor.fetchone()[0] or 0
            
            cursor = conn.execute("""
                SELECT SUM(estimated_cost) FROM usage_sessions 
                WHERE timestamp > datetime('now', '-7 days')
            """)
            week_spend = cursor.fetchone()[0] or 0
            
            daily_burn_rate = week_spend / 7 if week_spend > 0 else 0
            projected_spend = daily_burn_rate * days_remaining
            
            # Generate alerts
            alerts = []
            if remaining < 5:
                alerts.append("LOW_BUDGET")
            if projected_spend > remaining:
                alerts.append("BURN_RATE_HIGH")
            if days_remaining <= 1:
                alerts.append("PERIOD_ENDING")
            if today_spend > 2:
                alerts.append("DAILY_LIMIT_EXCEEDED")
        
        return {
            "total_budget": total,
            "remaining_budget": remaining,
            "used_budget": total - remaining,
            "days_remaining": days_remaining,
            "today_spend": round(today_spend, 4),
            "daily_burn_rate": round(daily_burn_rate, 4),
            "projected_spend": round(projected_spend, 4),
            "period_end": budget_info[4],
            "alerts": alerts,
            "budget_health": "GOOD" if not alerts else "WARNING" if len(alerts) < 3 else "CRITICAL"
        }
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """Get recent usage sessions."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT timestamp, model, input_tokens, output_tokens, estimated_cost, session_type, notes
                FROM usage_sessions 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
            
            return [
                {
                    "timestamp": row[0],
                    "model": row[1],
                    "input_tokens": row[2],
                    "output_tokens": row[3],
                    "estimated_cost": row[4],
                    "session_type": row[5],
                    "notes": row[6]
                }
                for row in cursor.fetchall()
            ]

# Convenience functions for MCP server integration
def record_usage(input_tokens: int, output_tokens: int, model: str = "claude-3-5-sonnet-20241022", 
                session_type: str = "interactive", notes: str = "") -> float:
    """Record usage and return estimated cost."""
    tracker = UsageTracker()
    return tracker.record_session(model, input_tokens, output_tokens, session_type, notes)

def get_budget_status() -> Dict:
    """Get current budget status."""
    tracker = UsageTracker()
    return tracker.get_budget_status()

def update_remaining_budget(amount: float) -> Dict:
    """Update remaining budget amount."""
    tracker = UsageTracker()
    return tracker.update_budget(amount)

if __name__ == "__main__":
    # Test the usage tracker
    tracker = UsageTracker()
    
    # Record a test session
    cost = tracker.record_session("claude-3-5-sonnet-20241022", 1000, 500, "test", "Testing usage tracker")
    print(f"Recorded test session, estimated cost: ${cost}")
    
    # Get budget status
    status = tracker.get_budget_status()
    print(f"Budget status: {json.dumps(status, indent=2)}")
    
    # Get usage summary
    summary = tracker.get_usage_summary(7)
    print(f"Usage summary: {json.dumps(summary, indent=2)}")