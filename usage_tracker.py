"""
Local usage tracking for Claude API costs and budget management.
Since Anthropic doesn't provide programmatic credit balance API,
we maintain local estimates and allow manual budget updates.
"""

import sqlite3
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger("mecris.usage")

@dataclass
class UsageSession:
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    session_type: str = "interactive"
    notes: str = ""

class UsageTracker:
    def __init__(self, db_path: str = "mecris_usage.db", user_id: str = None):
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        self.neon_url = os.getenv("NEON_DB_URL")
        self.user_id = user_id or os.getenv("DEFAULT_USER_ID")
        self.use_neon = False
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
        """Initialize database for usage tracking."""
        if self.neon_url:
            try:
                self._init_neon()
                self.use_neon = True
                logger.info("UsageTracker: Neon database initialized successfully.")
                return
            except Exception as e:
                logger.error(f"UsageTracker: Neon init failed: {e}. Fallback to SQLite is available but might be empty.")

        logger.warning(f"UsageTracker: Using SQLite fallback at {self.db_path}")
        self._init_sqlite()

    def _init_neon(self):
        """Initialize Neon PostgreSQL database."""
        with psycopg2.connect(self.neon_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS usage_sessions (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMPTZ NOT NULL,
                        model TEXT NOT NULL,
                        input_tokens INTEGER NOT NULL,
                        output_tokens INTEGER NOT NULL,
                        estimated_cost DOUBLE PRECISION NOT NULL,
                        session_type TEXT NOT NULL,
                        notes TEXT DEFAULT '',
                        user_id TEXT REFERENCES users(pocket_id_sub)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS budget_tracking (
                        user_id TEXT PRIMARY KEY REFERENCES users(pocket_id_sub),
                        total_budget DOUBLE PRECISION NOT NULL,
                        remaining_budget DOUBLE PRECISION NOT NULL,
                        budget_period_start TEXT NOT NULL,
                        budget_period_end TEXT NOT NULL,
                        last_updated TIMESTAMPTZ NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS goals (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        priority TEXT DEFAULT 'medium',
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMPTZ NOT NULL,
                        completed_at TIMESTAMPTZ DEFAULT NULL,
                        due_date TEXT DEFAULT NULL,
                        user_id TEXT REFERENCES users(pocket_id_sub)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS alert_log (
                        id SERIAL PRIMARY KEY,
                        alert_type TEXT NOT NULL,
                        alert_level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        sent_at TIMESTAMPTZ NOT NULL,
                        context TEXT DEFAULT '',
                        user_id TEXT REFERENCES users(pocket_id_sub)
                    )
                """)
                
                # Initialize budget if not exists
                if self.user_id:
                    cur.execute("SELECT COUNT(*) FROM budget_tracking WHERE user_id = %s", (self.user_id,))
                    if cur.fetchone()[0] == 0:
                        cur.execute("""
                            INSERT INTO budget_tracking 
                            (user_id, total_budget, remaining_budget, budget_period_start, budget_period_end, last_updated)
                            VALUES (%s, 24.96, 24.95, '2025-08-06', '2025-09-30', %s)
                        """, (self.user_id, datetime.now()))

    def _init_sqlite(self):
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
            
            # Initialize default budget if table is empty
            cursor = conn.execute("SELECT COUNT(*) FROM budget_tracking")
            if cursor.fetchone()[0] == 0:
                conn.execute("""
                    INSERT INTO budget_tracking 
                    (id, total_budget, remaining_budget, budget_period_start, budget_period_end, last_updated)
                    VALUES (1, 24.96, 24.95, '2025-08-06', '2025-09-30', ?)
                """, (datetime.now().isoformat(),))

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost for a session."""
        if model not in self.pricing:
            # Fallback to standard Sonnet pricing if model unknown
            pricing = self.pricing["claude-3-5-sonnet-20241022"]
        else:
            pricing = self.pricing[model]
            
        cost = (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])
        return round(cost, 6)

    def record_session(self, model: str, input_tokens: int, output_tokens: int, 
                      session_type: str = "interactive", notes: str = "", user_id: str = None) -> float:
        """Record a usage session and return estimated cost."""
        target_user_id = user_id or self.user_id
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        now = datetime.now()
        
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO usage_sessions 
                            (timestamp, model, input_tokens, output_tokens, estimated_cost, session_type, notes, user_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (now, model, input_tokens, output_tokens, cost, session_type, notes, target_user_id))
                        
                        # Update remaining budget
                        cur.execute("""
                            UPDATE budget_tracking 
                            SET remaining_budget = remaining_budget - %s, last_updated = %s
                            WHERE user_id = %s
                        """, (cost, now, target_user_id))
                return cost
            except Exception as e:
                logger.error(f"UsageTracker: Neon record_session failed: {e}")
                raise

        timestamp = now.isoformat()
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

    def get_budget_status(self, user_id: str = None) -> Dict:
        """Get current budget status with alerts."""
        target_user_id = user_id or self.user_id
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("SELECT * FROM budget_tracking WHERE user_id = %s", (target_user_id,))
                        budget_info = cur.fetchone()
                        
                        if not budget_info:
                            return {"error": f"No budget information found for {target_user_id} in Neon"}
                        
                        total, remaining = budget_info['total_budget'], budget_info['remaining_budget']
                        period_end_val = budget_info['budget_period_end']
                        if isinstance(period_end_val, str):
                            period_end = datetime.fromisoformat(period_end_val.replace('Z', '+00:00'))
                        else:
                            # If it is a date object from psycopg2
                            period_end = datetime.combine(period_end_val, datetime.min.time())
                            
                        days_remaining = (period_end.date() - date.today()).days
                        
                        # today spend
                        cur.execute("""
                            SELECT SUM(estimated_cost) FROM usage_sessions 
                            WHERE user_id = %s AND (timestamp::TIMESTAMPTZ AT TIME ZONE 'US/Eastern')::date = CURRENT_DATE AT TIME ZONE 'US/Eastern'
                        """, (target_user_id,))
                        today_spend = cur.fetchone()['sum'] or 0
                        
                        cur.execute("SELECT SUM(estimated_cost) FROM usage_sessions WHERE user_id = %s AND timestamp > NOW() - INTERVAL '7 days'", (target_user_id,))
                        week_spend = cur.fetchone()['sum'] or 0
                        
                        daily_burn_rate = week_spend / 7 if week_spend > 0 else 0
                        projected_spend = daily_burn_rate * days_remaining
                        
                        # Generate alerts
                        alerts = []
                        if remaining < 5: alerts.append("LOW_BUDGET")
                        if projected_spend > remaining: alerts.append("BURN_RATE_HIGH")
                        if days_remaining <= 1: alerts.append("PERIOD_ENDING")
                        if today_spend > 2: alerts.append("DAILY_LIMIT_EXCEEDED")
                        
                        return {
                            "total_budget": total,
                            "remaining_budget": remaining,
                            "used_budget": round(total - remaining, 2),
                            "days_remaining": days_remaining,
                            "today_spend": round(today_spend, 4),
                            "daily_burn_rate": round(daily_burn_rate, 4),
                            "projected_spend": round(projected_spend, 4),
                            "period_end": str(budget_info['budget_period_end']),
                            "alerts": alerts,
                            "budget_health": "GOOD" if not alerts else "WARNING" if len(alerts) < 3 else "CRITICAL"
                        }
            except Exception as e:
                logger.error(f"UsageTracker: Neon get_budget_status failed: {e}")
                raise

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
            "used_budget": round(total - remaining, 2),
            "days_remaining": days_remaining,
            "today_spend": round(today_spend, 4),
            "daily_burn_rate": round(daily_burn_rate, 4),
            "projected_spend": round(projected_spend, 4),
            "period_end": budget_info[4],
            "alerts": alerts,
            "budget_health": "GOOD" if not alerts else "WARNING" if len(alerts) < 3 else "CRITICAL"
        }

    def get_recent_sessions(self, limit: int = 10, user_id: str = None) -> List[Dict]:
        """Get the most recent usage sessions."""
        target_user_id = user_id or self.user_id
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT timestamp, model, input_tokens, output_tokens, estimated_cost, session_type, notes 
                            FROM usage_sessions 
                            WHERE user_id = %s
                            ORDER BY timestamp DESC 
                            LIMIT %s
                        """, (target_user_id, limit,))
                        sessions = cur.fetchall()
                        for s in sessions:
                            s['timestamp'] = s['timestamp'].isoformat()
                        return [dict(s) for s in sessions]
            except Exception as e:
                logger.error(f"UsageTracker: Neon get_recent_sessions failed: {e}")
                raise

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

    def update_budget(self, remaining_budget: float, total_budget: Optional[float] = None, 
                     period_end: Optional[str] = None, user_id: str = None) -> Dict:
        """Manually update budget information."""
        target_user_id = user_id or self.user_id
        now = datetime.now()
        timestamp = now.isoformat()
        
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        if total_budget and period_end:
                            cur.execute("""
                                UPDATE budget_tracking 
                                SET total_budget = %s, remaining_budget = %s, budget_period_end = %s, last_updated = %s
                                WHERE user_id = %s
                            """, (total_budget, remaining_budget, period_end, now, target_user_id))
                        else:
                            cur.execute("""
                                UPDATE budget_tracking 
                                SET remaining_budget = %s, last_updated = %s
                                WHERE user_id = %s
                            """, (remaining_budget, now, target_user_id))
                        
                        cur.execute("SELECT * FROM budget_tracking WHERE user_id = %s", (target_user_id,))
                        budget_info = cur.fetchone()
                        return {
                            "total": budget_info['total_budget'],
                            "remaining": budget_info['remaining_budget'],
                            "period_start": budget_info['budget_period_start'],
                            "period_end": budget_info['budget_period_end'],
                            "last_updated": str(budget_info['last_updated'])
                        }
            except Exception as e:
                logger.error(f"UsageTracker: Neon update_budget failed: {e}")
                raise

        with sqlite3.connect(self.db_path) as conn:
            if total_budget and period_end:
                conn.execute("""
                    UPDATE budget_tracking 
                    SET total_budget = ?, remaining_budget = ?, budget_period_end = ?, last_updated = ?
                    WHERE id = 1
                """, (total_budget, remaining_budget, period_end, timestamp))
            else:
                conn.execute("""
                    UPDATE budget_tracking 
                    SET remaining_budget = ?, last_updated = ?
                    WHERE id = 1
                """, (remaining_budget, timestamp))
            
            cursor = conn.execute("SELECT * FROM budget_tracking WHERE id = 1")
            budget_info = cursor.fetchone()
        
        return {
            "total": budget_info[1],
            "remaining": budget_info[2],
            "period_start": budget_info[3],
            "period_end": budget_info[4],
            "last_updated": budget_info[5]
        }

    def get_goals(self, user_id: str = None) -> List[Dict]:
        """Get all goals with their status."""
        target_user_id = user_id or self.user_id
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT id, title, description, priority, status, created_at, completed_at, due_date
                            FROM goals 
                            WHERE user_id = %s
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
                        """, (target_user_id,))
                        return [dict(row) for row in cur.fetchall()]
            except Exception as e:
                logger.error(f"UsageTracker: Neon get_goals failed: {e}")
                raise

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
                    "did_date": row[7],
                    "completed": row[4] == 'completed'
                }
                for row in cursor.fetchall()
            ]

    def complete_goal(self, goal_id: int, user_id: str = None) -> Dict:
        """Mark a goal as completed."""
        target_user_id = user_id or self.user_id
        now = datetime.now()
        timestamp = now.isoformat()
        
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("SELECT title FROM goals WHERE id = %s AND user_id = %s", (goal_id, target_user_id))
                        goal = cur.fetchone()
                        if goal:
                            cur.execute("""
                                UPDATE goals 
                                SET status = 'completed', completed_at = %s 
                                WHERE id = %s AND user_id = %s
                            """, (now, goal_id, target_user_id))
                            return {"completed": True, "goal_id": goal_id, "title": goal['title'], "completed_at": timestamp}
                        else:
                            return {"error": f"Goal {goal_id} not found for user {target_user_id}"}
            except Exception as e:
                logger.error(f"UsageTracker: Neon complete_goal failed: {e}")
                raise

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT title FROM goals WHERE id = ?", (goal_id,))
            goal = cursor.fetchone()
            if not goal: return {"error": f"Goal {goal_id} not found"}
            conn.execute("""
                UPDATE goals 
                SET status = 'completed', completed_at = ? 
                WHERE id = ?
            """, (timestamp, goal_id))
            return {"completed": True, "goal_id": goal_id, "title": goal[0], "completed_at": timestamp}

    def add_goal(self, title: str, description: str = "", priority: str = 'medium', due_date: Optional[str] = None, user_id: str = None) -> Dict:
        """Add a new goal."""
        target_user_id = user_id or self.user_id
        now = datetime.now()
        timestamp = now.isoformat()
        
        if priority not in ['high', 'medium', 'low']:
            priority = 'medium'
        
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO goals (title, description, priority, status, created_at, due_date, user_id)
                            VALUES (%s, %s, %s, 'active', %s, %s, %s)
                            RETURNING id
                        """, (title, description, priority, now, due_date, target_user_id))
                        goal_id = cur.fetchone()[0]
                        return {"added": True, "goal_id": goal_id, "title": title, "priority": priority, "created_at": timestamp}
            except Exception as e:
                logger.error(f"UsageTracker: Neon add_goal failed: {e}")
                raise

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO goals (title, description, priority, status, created_at, due_date)
                VALUES (?, ?, ?, 'active', ?, ?)
            """, (title, description, priority, timestamp, due_date))
            goal_id = cursor.lastrowid
            return {"added": True, "goal_id": goal_id, "title": title, "priority": priority, "created_at": timestamp}

    def should_send_alert(self, alert_type: str, alert_level: str, cooldown_minutes: int = 60, user_id: str = None) -> bool:
        """Check if an alert should be sent based on cooldown."""
        target_user_id = user_id or self.user_id
        cutoff = datetime.now() - timedelta(minutes=cooldown_minutes)
        
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT COUNT(*) FROM alert_log 
                            WHERE alert_type = %s AND alert_level = %s AND sent_at > %s AND user_id = %s
                        """, (alert_type, alert_level, cutoff, target_user_id))
                        return cur.fetchone()[0] == 0
            except Exception as e:
                logger.error(f"UsageTracker: Neon should_send_alert failed: {e}")
                raise

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM alert_log 
                WHERE alert_type = ? AND alert_level = ? AND sent_at > ?
            """, (alert_type, alert_level, cutoff.isoformat()))
            return cursor.fetchone()[0] == 0

    def log_alert(self, alert_type: str, alert_level: str, message: str, context: str = "", user_id: str = None):
        """Log a sent alert."""
        target_user_id = user_id or self.user_id
        now = datetime.now()
        
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO alert_log (alert_type, alert_level, message, sent_at, context, user_id)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (alert_type, alert_level, message, now, context, target_user_id))
                return
            except Exception as e:
                logger.error(f"UsageTracker: Neon log_alert failed: {e}")
                raise

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO alert_log (alert_type, alert_level, message, sent_at, context)
                VALUES (?, ?, ?, ?, ?)
            """, (alert_type, alert_level, message, now.isoformat(), context))

    def get_usage_summary(self, days: int = 7, user_id: str = None) -> Dict:
        """Get usage summary for the last N days."""
        target_user_id = user_id or self.user_id
        cutoff_date = (datetime.now() - timedelta(days=days))
        
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        # Daily usage
                        cur.execute("""
                            SELECT timestamp::date as date, SUM(estimated_cost) as cost
                            FROM usage_sessions 
                            WHERE user_id = %s AND timestamp > %s
                            GROUP BY timestamp::date
                            ORDER BY date DESC
                        """, (target_user_id, cutoff_date,))
                        
                        daily_usage = [dict(row) for row in cur.fetchall()]
                        for d in daily_usage:
                            d['date'] = str(d['date'])
                        
                        # Usage by session type
                        cur.execute("""
                            SELECT session_type, SUM(estimated_cost) as cost, COUNT(*) as count
                            FROM usage_sessions 
                            WHERE user_id = %s AND timestamp > %s
                            GROUP BY session_type
                        """, (target_user_id, cutoff_date,))
                        type_usage = {row['session_type']: {"cost": row['cost'], "count": row['count']} for row in cur.fetchall()}
                        
                        # Model breakdown
                        cur.execute("""
                            SELECT model, SUM(estimated_cost) as cost, COUNT(*) as count
                            FROM usage_sessions 
                            WHERE user_id = %s AND timestamp > %s
                            GROUP BY model
                        """, (target_user_id, cutoff_date,))
                        model_usage = {row['model']: {"cost": row['cost'], "count": row['count']} for row in cur.fetchall()}
                        
                        total_cost = sum(d['cost'] for d in daily_usage)
                        
                        return {
                            "period_days": days,
                            "total_cost": round(total_cost, 4),
                            "daily_usage": daily_usage,
                            "type_breakdown": type_usage,
                            "model_breakdown": model_usage
                        }
            except Exception as e:
                logger.error(f"UsageTracker: Neon get_usage_summary failed: {e}")
                raise

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DATE(timestamp) as date, SUM(estimated_cost)
                FROM usage_sessions 
                WHERE timestamp > ?
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """, (cutoff_date.isoformat(),))
            
            daily_usage = [{"date": row[0], "cost": row[1]} for row in cursor.fetchall()]
            
            # Usage by session type
            cursor = conn.execute("""
                SELECT session_type, SUM(estimated_cost), COUNT(*)
                FROM usage_sessions 
                WHERE timestamp > ?
                GROUP BY session_type
            """, (cutoff_date.isoformat(),))
            type_usage = {row[0]: {"cost": row[1], "count": row[2]} for row in cursor.fetchall()}
            
            # Model breakdown
            cursor = conn.execute("""
                SELECT model, SUM(estimated_cost), COUNT(*)
                FROM usage_sessions 
                WHERE timestamp > ?
                GROUP BY model
            """, (cutoff_date.isoformat(),))
            model_usage = {row[0]: {"cost": row[1], "count": row[2]} for row in cursor.fetchall()}
            
            total_cost = sum(d["cost"] for d in daily_usage)
        
        return {
            "period_days": days,
            "total_cost": round(total_cost, 4),
            "daily_usage": daily_usage,
            "type_breakdown": type_usage,
            "model_breakdown": model_usage
        }

# Global singleton instance
_tracker_instance = None

def get_tracker():
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = UsageTracker()
    return _tracker_instance

# Global convenience functions
def record_usage(input_tokens: int, output_tokens: int, model: str = "claude-3-5-sonnet-20241022", 
                session_type: str = "interactive", notes: str = "", user_id: str = None) -> float:
    tracker = get_tracker()
    return tracker.record_session(model, input_tokens, output_tokens, session_type, notes, user_id)

def get_budget_status(user_id: str = None) -> Dict:
    tracker = get_tracker()
    return tracker.get_budget_status(user_id)

def update_remaining_budget(amount: float, user_id: str = None) -> Dict:
    tracker = get_tracker()
    return tracker.update_budget(amount, user_id=user_id)

def get_goals(user_id: str = None) -> List[Dict]:
    tracker = get_tracker()
    return tracker.get_goals(user_id)

def add_goal(title: str, description: str = "", priority: str = "medium", due_date: Optional[str] = None, user_id: str = None) -> Dict:
    tracker = get_tracker()
    return tracker.add_goal(title, description, priority, due_date, user_id)

def complete_goal(goal_id: int, user_id: str = None) -> Dict:
    tracker = get_tracker()
    return tracker.complete_goal(goal_id, user_id)

if __name__ == "__main__":
    # Configure logging for standalone test
    logging.basicConfig(level=logging.INFO)
    
    tracker = UsageTracker()
    
    # Test recording
    cost = tracker.record_session("claude-3-5-sonnet-20241022", 1000, 500, notes="Standalone test")
    print(f"Recorded test session, estimated cost: ${cost:.4f}")
    
    # Get status
    status = tracker.get_budget_status()
    print(f"Budget status: {json.dumps(status, indent=2)}")
    
    # Get usage summary
    summary = tracker.get_usage_summary(7)
    print(f"Usage summary: {json.dumps(summary, indent=2)}")
