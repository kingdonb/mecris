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
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT NULL,
                    due_date TEXT DEFAULT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    alert_level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    context TEXT DEFAULT ''
                )
            """)
            
            # Initialize budget if not exists
            cursor = conn.execute("SELECT COUNT(*) FROM budget_tracking")
            if cursor.fetchone()[0] == 0:
                # Default budget from your context: $13.92 remaining until Aug 5
                conn.execute("""
                    INSERT INTO budget_tracking 
                    (id, total_budget, remaining_budget, budget_period_start, budget_period_end, last_updated)
                    VALUES (1, 20.26, 13.92, '2025-08-01', '2025-08-05', ?)
                """, (datetime.now().isoformat(),))
            
            # Initialize mock goals if not exists
            cursor = conn.execute("SELECT COUNT(*) FROM goals")
            if cursor.fetchone()[0] == 0:
                mock_goals = [
                    ("Finish KubeCon abstract draft", "Complete the KubeCon proposal with clear value proposition", "high", "active", "2025-08-03"),
                    ("Test Twilio integration", "Verify SMS alerts work correctly for beemergencies and budget alerts", "high", "active", None),
                    ("Complete Obsidian MCP integration", "Get goals and todos reading from Obsidian vault", "medium", "active", "2025-08-04"),
                    ("Optimize budget burn rate", "Use remaining Claude credits effectively without waste", "high", "active", "2025-08-05"),
                    ("Document Mecris control loop", "Create comprehensive documentation for the accountability system", "medium", "active", None),
                    ("Set up goal completion workflow", "Create scripts to check off goals like budget updates", "low", "active", None)
                ]
                
                for title, desc, priority, status, due_date in mock_goals:
                    conn.execute("""
                        INSERT INTO goals (title, description, priority, status, created_at, due_date)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (title, desc, priority, status, datetime.now().isoformat(), due_date))
    
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
    
    def get_goals(self) -> List[Dict]:
        """Get all goals with their status."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, title, description, priority, status, created_at, completed_at, due_date
                FROM goals 
                ORDER BY 
                    CASE priority 
                        WHEN 'high' THEN 1 
                        WHEN 'medium' THEN 2 
                        WHEN 'low' THEN 3 
                    END,
                    CASE status
                        WHEN 'active' THEN 1
                        WHEN 'completed' THEN 2
                    END,
                    created_at
            """)
            
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "priority": row[3],
                    "status": row[4],
                    "created_at": row[5],
                    "completed_at": row[6],
                    "due_date": row[7],
                    "completed": row[4] == "completed"
                }
                for row in cursor.fetchall()
            ]
    
    def complete_goal(self, goal_id: int) -> Dict:
        """Mark a goal as completed."""
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Check if goal exists
            cursor = conn.execute("SELECT title FROM goals WHERE id = ?", (goal_id,))
            goal = cursor.fetchone()
            
            if not goal:
                return {"error": f"Goal {goal_id} not found"}
            
            # Mark as completed
            conn.execute("""
                UPDATE goals 
                SET status = 'completed', completed_at = ? 
                WHERE id = ?
            """, (timestamp, goal_id))
            
            return {
                "completed": True,
                "goal_id": goal_id,
                "title": goal[0],
                "completed_at": timestamp
            }
    
    def add_goal(self, title: str, description: str = "", priority: str = "medium", due_date: Optional[str] = None) -> Dict:
        """Add a new goal."""
        timestamp = datetime.now().isoformat()
        
        if priority not in ["high", "medium", "low"]:
            priority = "medium"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO goals (title, description, priority, status, created_at, due_date)
                VALUES (?, ?, ?, 'active', ?, ?)
            """, (title, description, priority, timestamp, due_date))
            
            goal_id = cursor.lastrowid
            
            return {
                "added": True,
                "goal_id": goal_id,
                "title": title,
                "priority": priority,
                "created_at": timestamp
            }
    
    def should_send_alert(self, alert_type: str, alert_level: str, cooldown_minutes: int = 60) -> bool:
        """Check if an alert should be sent based on cooldown period."""
        cutoff_time = (datetime.now() - timedelta(minutes=cooldown_minutes)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM alert_log 
                WHERE alert_type = ? AND alert_level = ? AND sent_at > ?
            """, (alert_type, alert_level, cutoff_time))
            
            recent_alerts = cursor.fetchone()[0]
            return recent_alerts == 0
    
    def log_alert(self, alert_type: str, alert_level: str, message: str, context: str = "") -> None:
        """Log an alert that was sent."""
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO alert_log (alert_type, alert_level, message, sent_at, context)
                VALUES (?, ?, ?, ?, ?)
            """, (alert_type, alert_level, message, timestamp, context))
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Get recent alerts sent."""
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT alert_type, alert_level, message, sent_at, context
                FROM alert_log 
                WHERE sent_at > ?
                ORDER BY sent_at DESC
            """, (cutoff_time,))
            
            return [
                {
                    "type": row[0],
                    "level": row[1],
                    "message": row[2],
                    "sent_at": row[3],
                    "context": row[4]
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

def get_goals() -> List[Dict]:
    """Get all goals."""
    tracker = UsageTracker()
    return tracker.get_goals()

def complete_goal(goal_id: int) -> Dict:
    """Complete a goal."""
    tracker = UsageTracker()
    return tracker.complete_goal(goal_id)

def add_goal(title: str, description: str = "", priority: str = "medium", due_date: Optional[str] = None) -> Dict:
    """Add a new goal."""
    tracker = UsageTracker()
    return tracker.add_goal(title, description, priority, due_date)

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