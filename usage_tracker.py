"""
Local usage tracking for Claude API costs and budget management.
Since Anthropic doesn't provide programmatic credit balance API,
we maintain local estimates and allow manual budget updates.
"""

import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import os
import logging

from services.credentials_manager import credentials_manager
from services.encryption_service import EncryptionService

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
    def __init__(self, user_id: str = None):
        self.neon_url = os.getenv("NEON_DB_URL")
        self.user_id = credentials_manager.resolve_user_id(user_id)
        self.use_neon = False
        self.encryption = EncryptionService()
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
                import psycopg2
                self._init_neon()
                self.use_neon = True
                logger.info("UsageTracker: Neon database initialized successfully.")
                return
            except Exception as e:
                logger.error(f"UsageTracker: Neon init failed: {e}. SQLite fallback is disabled.")
                raise ConnectionError(f"Critical error: Neon database is required but unreachable: {e}")
        else:
            logger.error("UsageTracker: NEON_DB_URL not found. System is in read-only or limited mode.")
            raise EnvironmentError("NEON_DB_URL must be set. SQLite fallback is no longer supported.")

    def _init_neon(self):
        """Initialize Neon PostgreSQL database."""
        import psycopg2
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
                        id SERIAL PRIMARY KEY,
                        user_id TEXT UNIQUE REFERENCES users(pocket_id_sub),
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
                    CREATE TABLE IF NOT EXISTS user_presence (
                        user_id TEXT PRIMARY KEY REFERENCES users(pocket_id_sub),
                        last_human_activity TIMESTAMPTZ,
                        last_ghost_activity TIMESTAMPTZ,
                        status TEXT DEFAULT 'silent'
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

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS message_log (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT REFERENCES users(pocket_id_sub) ON DELETE CASCADE,
                        date DATE DEFAULT CURRENT_DATE,
                        type TEXT NOT NULL,
                        sent_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        content TEXT,
                        status TEXT,
                        error_msg TEXT,
                        channel TEXT DEFAULT 'whatsapp'
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS autonomous_turns (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        agent_type TEXT NOT NULL,
                        agenda_slug TEXT NOT NULL,
                        input_tokens INTEGER NOT NULL,
                        output_tokens INTEGER NOT NULL,
                        cost DOUBLE PRECISION NOT NULL,
                        summary TEXT,
                        outcome TEXT,
                        container_id TEXT,
                        user_id TEXT REFERENCES users(pocket_id_sub)
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS token_bank (
                        user_id TEXT PRIMARY KEY REFERENCES users(pocket_id_sub),
                        available_tokens BIGINT NOT NULL DEFAULT 0,
                        monthly_limit BIGINT NOT NULL DEFAULT 1000000,
                        last_refill TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                
                # Initialize budget if not exists
                if self.user_id:
                    cur.execute("SELECT COUNT(*) FROM budget_tracking WHERE user_id = %s", (self.user_id,))
                    row = cur.fetchone()
                    if row and row[0] == 0:
                        cur.execute("""
                            INSERT INTO budget_tracking 
                            (user_id, total_budget, remaining_budget, budget_period_start, budget_period_end, last_updated)
                            VALUES (%s, 24.96, 24.95, '2025-08-06', '2025-09-30', %s)
                        """, (self.user_id, datetime.now()))

    def resolve_user_id(self, user_id: str) -> str:
        """Resolve familiar_id to pocket_id_sub."""
        if not self.use_neon or not user_id:
            return user_id or self.user_id
            
        try:
            import psycopg2
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT pocket_id_sub FROM users WHERE familiar_id = %s", (user_id,))
                    row = cur.fetchone()
                    if row:
                        return row[0]
        except Exception as e:
            logger.error(f"UsageTracker: resolve_user_id failed: {e}")
            
        return user_id

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
        target_user_id = self.resolve_user_id(user_id)
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        now = datetime.now()
        
        # Encrypt notes if they are not empty and encryption is active
        stored_notes = notes
        if notes and self.encryption.aesgcm:
            try:
                stored_notes = self.encryption.encrypt(notes)
            except Exception as e:
                logger.error(f"UsageTracker: Failed to encrypt session notes: {e}")
        
        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO usage_sessions 
                            (timestamp, model, input_tokens, output_tokens, estimated_cost, session_type, notes, user_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (now, model, input_tokens, output_tokens, cost, session_type, stored_notes, target_user_id))
                        
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

        raise RuntimeError("UsageTracker: Neon connection not active. Cannot record session.")

    def get_budget_status(self, user_id: str = None) -> Dict:
        """Get current budget status with alerts."""
        target_user_id = self.resolve_user_id(user_id)
        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
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

        raise RuntimeError("UsageTracker: Neon connection not active. Cannot get budget status.")

    def get_recent_sessions(self, limit: int = 10, user_id: str = None) -> List[Dict]:
        """Get the most recent usage sessions."""
        target_user_id = self.resolve_user_id(user_id)
        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
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
                        results = []
                        for s in sessions:
                            s_dict = dict(s)
                            s_dict['timestamp'] = s_dict['timestamp'].isoformat()
                            
                            # Decrypt notes if encrypted
                            if s_dict.get('notes') and self.encryption.aesgcm:
                                try:
                                    s_dict['notes'] = self.encryption.decrypt(s_dict['notes'])
                                except Exception:
                                    # Fallback if decryption fails (e.g. legacy plaintext data)
                                    pass
                            results.append(s_dict)
                        return results
            except Exception as e:
                logger.error(f"UsageTracker: Neon get_recent_sessions failed: {e}")
                raise

        raise RuntimeError("UsageTracker: Neon connection not active. Cannot get recent sessions.")

    def update_budget(self, remaining_budget: float, total_budget: Optional[float] = None, 
                     period_end: Optional[str] = None, user_id: str = None) -> Dict:
        """Manually update budget information."""
        target_user_id = self.resolve_user_id(user_id)
        now = datetime.now()
        
        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
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

        raise RuntimeError("UsageTracker: Neon connection not active. Cannot update budget.")

    def get_goals(self, user_id: str = None) -> List[Dict]:
        """Get all goals with their status."""
        target_user_id = self.resolve_user_id(user_id)
        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
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

        raise RuntimeError("UsageTracker: Neon connection not active. Cannot get goals.")

    def complete_goal(self, goal_id: int, user_id: str = None) -> Dict:
        """Mark a goal as completed."""
        target_user_id = self.resolve_user_id(user_id)
        now = datetime.now()
        timestamp = now.isoformat()
        
        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
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

        raise RuntimeError("UsageTracker: Neon connection not active. Cannot complete goal.")

    def add_goal(self, title: str, description: str = "", priority: str = 'medium', due_date: Optional[str] = None, user_id: str = None) -> Dict:
        """Add a new goal."""
        target_user_id = self.resolve_user_id(user_id)
        now = datetime.now()
        timestamp = now.isoformat()
        
        if priority not in ['high', 'medium', 'low']:
            priority = 'medium'
        
        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
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

        raise RuntimeError("UsageTracker: Neon connection not active. Cannot add goal.")

    def should_send_alert(self, alert_type: str, alert_level: str, cooldown_minutes: int = 60, user_id: str = None) -> bool:
        """Check if an alert should be sent based on cooldown."""
        target_user_id = self.resolve_user_id(user_id)
        cutoff = datetime.now() - timedelta(minutes=cooldown_minutes)
        
        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
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

        return True # Default to True if can't check log

    def log_alert(self, alert_type: str, alert_level: str, message: str, context: str = "", user_id: str = None):
        """Log a sent alert."""
        target_user_id = self.resolve_user_id(user_id)
        now = datetime.now()
        
        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
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

    def record_autonomous_turn(self, agent_type: str, agenda_slug: str, input_tokens: int, output_tokens: int, 
                               cost: float, summary: str, outcome: str = "success", container_id: str = "local", 
                               user_id: str = None):
        """Record an autonomous turn and encrypt the summary/outcome if possible."""
        target_user_id = self.resolve_user_id(user_id)
        now = datetime.now()
        
        # Encrypt PII fields (summary, outcome) before storing
        stored_summary = self.encryption.try_encrypt(summary)
        stored_outcome = self.encryption.try_encrypt(outcome)

        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO autonomous_turns 
                            (timestamp, agent_type, agenda_slug, input_tokens, output_tokens, cost, summary, outcome, container_id, user_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (now, agent_type, agenda_slug, input_tokens, output_tokens, cost, stored_summary, stored_outcome, container_id, target_user_id))
                return
            except Exception as e:
                logger.error(f"UsageTracker: Neon record_autonomous_turn failed: {e}")
                raise

        raise RuntimeError("UsageTracker: Neon connection not active. Cannot record autonomous turn.")

    def get_user_preferences(self, user_id: str = None) -> Dict[str, Any]:
        """Fetch user preferences including encrypted phone and notification settings."""
        target_user_id = self.resolve_user_id(user_id)
        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT phone_number_encrypted, timezone, notification_prefs, vacation_mode_until
                            FROM users WHERE pocket_id_sub = %s
                        """, (target_user_id,))
                        row = cur.fetchone()
                        if row:
                            res = dict(row)
                            if res.get('notification_prefs') and isinstance(res['notification_prefs'], str):
                                res['notification_prefs'] = json.loads(res['notification_prefs'])
                            return res
            except Exception as e:
                logger.error(f"UsageTracker: Neon get_user_preferences failed: {e}")
        return {}

    def get_usage_summary(self, days: int = 7, user_id: str = None) -> Dict:
        """Get usage summary for the last N days."""
        target_user_id = self.resolve_user_id(user_id)
        cutoff_date = (datetime.now() - timedelta(days=days))
        
        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
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

        raise RuntimeError("UsageTracker: Neon connection not active. Cannot get usage summary.")

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
