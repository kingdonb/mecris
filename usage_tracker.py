"""
Local usage tracking for Claude API costs and budget management.
Since Anthropic doesn't provide programmatic credit balance API,
we maintain local estimates and allow manual budget updates.
"""

import json
from datetime import datetime, timedelta, date, timezone
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


SOURCE_TYPES = ("api_credit", "subscription", "retired", "helix_grant")
GRANT_ENDING_DAYS = 14


def _evaluate_subscription(total: float, remaining: float, period_end: date, today: date,
                           today_spend: float, plan: Optional[str],
                           monthly_price_usd: Optional[float]) -> Dict:
    """A plan grant (e.g. Claude Ultra): no dollars are spent from it, only its end matters."""
    raw_days = (period_end - today).days
    ended = raw_days < 0
    if ended:
        health, alerts = "ENDED", ["GRANT_ENDED"]
    elif raw_days <= GRANT_ENDING_DAYS:
        health, alerts = "ENDING", ["GRANT_ENDING"]
    else:
        health, alerts = "GOOD", []
    days_left = max(raw_days, 0)
    return {
        "source_type": "subscription",
        "plan": plan,
        "monthly_price_usd": monthly_price_usd,
        "total_budget": total,
        "remaining_budget": remaining,
        "used_budget": round(total - remaining, 2),
        "days_remaining": days_left,
        "days_to_grant_end": days_left,
        "days_since_grant_end": -raw_days if ended else 0,
        "grant_end": period_end.isoformat(),
        "grant_ended": ended,
        "period_expired": False,
        "days_since_period_end": 0,
        "today_spend": round(today_spend, 4),
        "daily_burn_rate": 0.0,
        "projected_spend": 0.0,
        "alerts": alerts,
        "budget_health": health,
    }


def evaluate_budget(total: float, remaining: float, period_end: date, today: date,
                    today_spend: float = 0.0, week_spend: float = 0.0,
                    source_type: str = "api_credit", plan: Optional[str] = None,
                    monthly_price_usd: Optional[float] = None) -> Dict:
    """Derive budget health from a stored budget row (kingdonb/mecris#345).

    api_credit (default): a dollar budget. A period whose end date has passed
    is *expired*, not exhausted: the row simply hasn't been updated. It reports
    STALE / PERIOD_EXPIRED, days_remaining is clamped to 0 (never negative
    "days left"), and no spend-pressure alerts fire.

    subscription: a plan grant whose window is the period columns. GOOD while
    it runs, ENDING within GRANT_ENDING_DAYS of its end, ENDED after it. Spend
    never moves it.

    retired: no budget is tracked any more. RETIRED, no alerts.
    Dollar fields stay numeric in every branch for the Rust and web readers.
    """
    if source_type == "subscription":
        return _evaluate_subscription(total, remaining, period_end, today, today_spend,
                                      plan, monthly_price_usd)
    if source_type == "retired":
        return {
            "source_type": "retired",
            "plan": plan,
            "monthly_price_usd": monthly_price_usd,
            "total_budget": total,
            "remaining_budget": remaining,
            "used_budget": round(total - remaining, 2),
            "days_remaining": 0,
            "period_expired": False,
            "days_since_period_end": 0,
            "today_spend": round(today_spend, 4),
            "daily_burn_rate": 0.0,
            "projected_spend": 0.0,
            "alerts": [],
            "budget_health": "RETIRED",
        }

    raw_days = (period_end - today).days
    expired = raw_days < 0
    days_remaining = max(raw_days, 0)
    daily_burn_rate = week_spend / 7 if week_spend > 0 else 0
    projected_spend = daily_burn_rate * days_remaining

    if expired:
        alerts = ["PERIOD_EXPIRED"]
        health = "STALE"
    else:
        alerts = []
        if remaining < 5: alerts.append("LOW_BUDGET")
        if projected_spend > remaining: alerts.append("BURN_RATE_HIGH")
        if days_remaining <= 1: alerts.append("PERIOD_ENDING")
        if today_spend > 2: alerts.append("DAILY_LIMIT_EXCEEDED")
        health = "GOOD" if not alerts else "WARNING" if len(alerts) < 3 else "CRITICAL"

    return {
        "source_type": "api_credit",
        "total_budget": total,
        "remaining_budget": remaining,
        "used_budget": round(total - remaining, 2),
        "days_remaining": days_remaining,
        "period_expired": expired,
        "days_since_period_end": -raw_days if expired else 0,
        "today_spend": round(today_spend, 4),
        "daily_burn_rate": round(daily_burn_rate, 4),
        "projected_spend": round(projected_spend, 4),
        "alerts": alerts,
        "budget_health": health,
    }

def _add_months(d: date, months: int) -> date:
    import calendar
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def evaluate_helix_grant(grant: float, period_start: datetime, period_end: datetime,
                         burned: Optional[float], balance: Optional[float], now: datetime,
                         target_balance: Optional[float] = None,
                         target_date: Optional[date] = None) -> Dict:
    """The budget as the Helix monthly grant (kingdonb/mecris#393).

    The period is the wallet's own, so it rolls over by itself and is never
    stale. Used is what the balance dropped since the period started (inflows
    excluded); spending past the grant is allowed and raises nothing: this
    tracks, it does not ration. With a target (balance by date), the pace is
    what has to be spent per day to get there, counting the grants still due.
    """
    import math
    days_remaining = max(0, math.ceil((period_end - now).total_seconds() / 86400))
    known = burned is not None and balance is not None
    used = round(burned, 2) if burned is not None else None
    target = pace = None
    if target_balance is not None and target_date is not None and target_date > now.date():
        grants_before, k = 0, 0
        while _add_months(period_end.date(), k) <= target_date:
            grants_before, k = grants_before + 1, k + 1
        target = {"balance": target_balance, "date": target_date.isoformat(), "grants_before": grants_before}
        if balance is not None:
            days = (target_date - now.date()).days
            pace = round(max(0.0, (balance + grants_before * grant - target_balance) / days), 2)
    return {
        "source_type": "helix_grant",
        "total_budget": grant,
        "remaining_budget": round(max(0.0, grant - burned), 2) if burned is not None else None,
        "used_budget": used,
        "days_remaining": days_remaining,
        "period_start": period_start.date().isoformat(),
        "period_end": period_end.date().isoformat(),
        "period_expired": False,
        "days_since_period_end": 0,
        "helix_balance": round(balance, 2) if balance is not None else None,
        "target": target,
        "target_pace_per_day": pace,
        "alerts": [],
        "budget_health": "GOOD" if known else "UNKNOWN",
    }


class UsageTracker:
    def __init__(self, user_id: str = None):
        self.neon_url = os.getenv("NEON_DB_URL")
        self.user_id = credentials_manager.resolve_user_id(user_id)
        self._use_neon = False
        self._db_initialized = False
        self.encryption = EncryptionService()
        
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
    
    @property
    def use_neon(self) -> bool:
        if not self._db_initialized:
            self.ensure_db_initialized()
        return self._use_neon

    @use_neon.setter
    def use_neon(self, value: bool):
        self._use_neon = value
        if value:
            self._db_initialized = True

    def ensure_db_initialized(self):
        if not self._db_initialized:
            self._db_initialized = True
            self.init_database()

    def init_database(self):
        """Initialize database for usage tracking."""
        if self.neon_url:
            try:
                import psycopg2
                self._init_neon()
                self._use_neon = True
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
                # No budget row is seeded: a missing row reads as "Budget: unknown",
                # and update_budget creates one (kingdonb/mecris#345).

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
                        
                        # Decrement only a dollar (api_credit) budget; a subscription
                        # grant is not spent per token (kingdonb/mecris#345). Before the
                        # v9 migration the column is absent and every row is api_credit.
                        cur.execute("SAVEPOINT budget_decrement")
                        try:
                            cur.execute("""
                                UPDATE budget_tracking
                                SET remaining_budget = remaining_budget - %s, last_updated = %s
                                WHERE user_id = %s AND COALESCE(source_type, 'api_credit') = 'api_credit'
                            """, (cost, now, target_user_id))
                            cur.execute("RELEASE SAVEPOINT budget_decrement")
                        except psycopg2.errors.UndefinedColumn:
                            cur.execute("ROLLBACK TO SAVEPOINT budget_decrement")
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
                        
                        if (budget_info.get('source_type') or 'api_credit') == 'helix_grant':
                            return self._helix_grant_status(target_user_id, float(budget_info['total_budget']))

                        total, remaining = budget_info['total_budget'], budget_info['remaining_budget']
                        period_end_val = budget_info['budget_period_end']
                        if isinstance(period_end_val, str):
                            period_end = datetime.fromisoformat(period_end_val.replace('Z', '+00:00'))
                        else:
                            # If it is a date object from psycopg2
                            period_end = datetime.combine(period_end_val, datetime.min.time())
                            
                        # today spend
                        cur.execute("""
                            SELECT SUM(estimated_cost) FROM usage_sessions 
                            WHERE user_id = %s AND (timestamp::TIMESTAMPTZ AT TIME ZONE 'America/New_York')::date = CURRENT_DATE AT TIME ZONE 'America/New_York'
                        """, (target_user_id,))
                        today_spend = cur.fetchone()['sum'] or 0
                        
                        cur.execute("SELECT SUM(estimated_cost) FROM usage_sessions WHERE user_id = %s AND timestamp > NOW() - INTERVAL '7 days'", (target_user_id,))
                        week_spend = cur.fetchone()['sum'] or 0
                        
                        # Rows from before the v9 migration have no source_type: api_credit.
                        source_type = budget_info.get('source_type') or 'api_credit'
                        return {
                            **evaluate_budget(total, remaining, period_end.date(), date.today(), today_spend, week_spend,
                                              source_type=source_type, plan=budget_info.get('plan'),
                                              monthly_price_usd=budget_info.get('monthly_price_usd')),
                            "period_start": str(budget_info.get('budget_period_start')),
                            "period_end": str(budget_info['budget_period_end']),
                        }
            except Exception as e:
                logger.error(f"UsageTracker: Neon get_budget_status failed: {e}")
                raise

        raise RuntimeError("UsageTracker: Neon connection not active. Cannot get budget status.")

    def _helix_grant_status(self, target_user_id: str, grant: float) -> Dict:
        """#393: the Helix grant budget, from the wallet's period and the balance log.
        The stored period columns are not used, so the budget never goes stale.
        HELIX_TARGET_BALANCE / HELIX_TARGET_DATE (YYYY-MM-DD) set an optional target."""
        from scripts import helix_billing, helix_balance_scraper
        now = datetime.now(timezone.utc)
        wallet = helix_billing.get_wallet()
        target_balance = target_date = None
        try:
            if os.getenv("HELIX_TARGET_DATE"):
                target_date = date.fromisoformat(os.getenv("HELIX_TARGET_DATE"))
                target_balance = float(os.getenv("HELIX_TARGET_BALANCE", "0"))
        except ValueError:
            logger.warning("HELIX_TARGET_DATE / HELIX_TARGET_BALANCE not understood; no target")
            target_balance = target_date = None
        if not wallet or not wallet.get("period_start") or not wallet.get("period_end"):
            return {
                "source_type": "helix_grant", "total_budget": grant, "remaining_budget": None,
                "used_budget": None, "days_remaining": None, "period_start": None, "period_end": None,
                "period_expired": False, "days_since_period_end": 0, "helix_balance": None,
                "target": None, "target_pace_per_day": None, "alerts": [], "budget_health": "UNKNOWN",
            }
        start = datetime.fromtimestamp(float(wallet["period_start"]), timezone.utc)
        end = datetime.fromtimestamp(float(wallet["period_end"]), timezone.utc)
        balance = float(wallet["balance"]) if wallet.get("balance") is not None else None
        burned = helix_balance_scraper.burned_since(target_user_id, start)
        return evaluate_helix_grant(grant, start, end, burned, balance, now,
                                    target_balance=target_balance, target_date=target_date)

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

    def update_budget(self, remaining_budget: Optional[float] = None, total_budget: Optional[float] = None,
                     period_end: Optional[str] = None, user_id: str = None, *,
                     period_start: Optional[str] = None, source_type: Optional[str] = None,
                     plan: Optional[str] = None, monthly_price_usd: Optional[float] = None) -> Dict:
        """Manually update budget information (kingdonb/mecris#345).

        Every argument is optional; only the fields given are written. source_type
        is api_credit (a dollar budget), subscription (a plan grant whose window is
        period_start..period_end) or retired. source_type, plan and
        monthly_price_usd need scripts/migrate_v9_subscription_budget.py. When the
        user has no row yet, one is created (period_end is then required).
        """
        if source_type is not None and source_type not in SOURCE_TYPES:
            return {"error": f"source_type must be one of {', '.join(SOURCE_TYPES)}"}
        if monthly_price_usd is not None and monthly_price_usd < 0:
            return {"error": "monthly_price_usd must not be negative"}
        fields = [
            ("total_budget", total_budget),
            ("remaining_budget", remaining_budget),
            ("budget_period_start", period_start),
            ("budget_period_end", period_end),
            ("source_type", source_type),
            ("plan", plan),
            ("monthly_price_usd", monthly_price_usd),
        ]
        fields = [(column, value) for column, value in fields if value is not None]
        if not fields:
            return {"error": "Nothing to update: give at least one budget field"}

        target_user_id = self.resolve_user_id(user_id)
        now = datetime.now(timezone.utc)

        if self.use_neon:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        assignments = ", ".join(f"{column} = %s" for column, _ in fields)
                        cur.execute(
                            f"UPDATE budget_tracking SET {assignments}, last_updated = %s WHERE user_id = %s",
                            tuple(value for _, value in fields) + (now, target_user_id),
                        )
                        if cur.rowcount == 0:
                            if period_end is None:
                                return {"error": "No budget row yet: give period_end to create one"}
                            values = dict(fields)
                            total = values.get("total_budget", remaining_budget or 0.0)
                            values.setdefault("total_budget", total)
                            values.setdefault("remaining_budget", total)
                            values.setdefault("budget_period_start", date.today().isoformat())
                            columns = list(values)
                            cur.execute(
                                f"INSERT INTO budget_tracking (user_id, {', '.join(columns)}, last_updated) "
                                f"VALUES (%s, {', '.join(['%s'] * len(columns))}, %s)",
                                (target_user_id, *values.values(), now),
                            )

                        cur.execute("SELECT * FROM budget_tracking WHERE user_id = %s", (target_user_id,))
                        budget_info = cur.fetchone()
                        return {
                            "total": budget_info['total_budget'],
                            "remaining": budget_info['remaining_budget'],
                            "period_start": budget_info['budget_period_start'],
                            "period_end": budget_info['budget_period_end'],
                            "source_type": budget_info.get('source_type') or 'api_credit',
                            "plan": budget_info.get('plan'),
                            "monthly_price_usd": budget_info.get('monthly_price_usd'),
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
