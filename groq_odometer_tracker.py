#!/usr/bin/env python3
"""
Groq Odometer Tracker - Solving the monthly cumulative usage problem

This system tracks Groq's monotonically increasing monthly usage (odometer)
and intelligently handles month boundaries, missed readings, and reminder scheduling.
"""

import sqlite3
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("groq_odometer")

class OdometerStatus(Enum):
    NORMAL = "normal"              # Mid-month, tracking normally
    APPROACHING_RESET = "approaching"  # Last 3 days of month
    NEEDS_READING = "needs_reading"   # User should input current value
    RESET_DETECTED = "reset_detected" # Odometer has reset to 0
    STALE = "stale"                # No reading for >7 days

@dataclass
class OdometerReading:
    timestamp: str
    month: str  # YYYY-MM format
    value: float  # Cumulative cost for the month
    is_final: bool  # True if this is the last reading of the month
    notes: str = ""

class GroqOdometerTracker:
    def __init__(self, db_path: str = "mecris_virtual_budget.db"):
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        self.neon_url = os.getenv("NEON_DB_URL")
        self.use_neon = False
        self.init_database()
        
    def init_database(self):
        """Initialize odometer tracking tables."""
        if self.neon_url:
            try:
                import psycopg2
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS groq_odometer_readings (
                                id SERIAL PRIMARY KEY,
                                timestamp TIMESTAMPTZ NOT NULL,
                                month TEXT NOT NULL,
                                cumulative_value DOUBLE PRECISION NOT NULL,
                                is_final_reading BOOLEAN DEFAULT FALSE,
                                is_reset BOOLEAN DEFAULT FALSE,
                                notes TEXT DEFAULT '',
                                created_at TIMESTAMPTZ NOT NULL
                            )
                        """)
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS groq_monthly_summaries (
                                month TEXT PRIMARY KEY,
                                total_cost DOUBLE PRECISION NOT NULL,
                                first_reading_date DATE,
                                last_reading_date DATE,
                                reading_count INTEGER,
                                finalized BOOLEAN DEFAULT FALSE,
                                created_at TIMESTAMPTZ NOT NULL,
                                updated_at TIMESTAMPTZ NOT NULL
                            )
                        """)
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS groq_reminders (
                                id SERIAL PRIMARY KEY,
                                reminder_type TEXT NOT NULL,
                                scheduled_for DATE NOT NULL,
                                sent BOOLEAN DEFAULT FALSE,
                                sent_at TIMESTAMPTZ,
                                response TEXT,
                                created_at TIMESTAMPTZ NOT NULL
                            )
                        """)
                self.use_neon = True
                logger.info("GroqOdometerTracker: Neon database initialized successfully.")
                return
            except Exception as e:
                logger.error(f"GroqOdometerTracker: Neon init failed: {e}. Fallback to SQLite is available but might be empty.")

        if not self.use_neon:
            logger.warning(f"GroqOdometerTracker: Using SQLite fallback at {self.db_path}")
            with sqlite3.connect(self.db_path) as conn:
                # Odometer readings table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS groq_odometer_readings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        month TEXT NOT NULL,
                        cumulative_value REAL NOT NULL,
                        is_final_reading BOOLEAN DEFAULT FALSE,
                        is_reset BOOLEAN DEFAULT FALSE,
                        notes TEXT DEFAULT '',
                        created_at TEXT NOT NULL
                    )
                """)
                
                # Monthly summaries for reconciliation
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS groq_monthly_summaries (
                        month TEXT PRIMARY KEY,
                        total_cost REAL NOT NULL,
                        first_reading_date TEXT,
                        last_reading_date TEXT,
                        reading_count INTEGER,
                        finalized BOOLEAN DEFAULT FALSE,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                
                # Reminder tracking
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS groq_reminders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reminder_type TEXT NOT NULL,
                        scheduled_for DATE NOT NULL,
                        sent BOOLEAN DEFAULT FALSE,
                        sent_at TEXT,
                        response TEXT,
                        created_at TEXT NOT NULL
                    )
                """)
    
    def record_odometer_reading(self, value: float, notes: str = "", month: Optional[str] = None) -> Dict:
        """Record a new odometer reading, handling month boundaries intelligently."""
        now = datetime.now()
        target_month = month if month else now.strftime("%Y-%m")
        
        # Check for odometer reset (only for current month recordings)
        last_reading = self.get_last_reading()
        reset_detected = False
        
        if last_reading and not month:
            last_month = last_reading['month']
            last_value = last_reading['value']
            
            if value < last_value and target_month != last_month:
                reset_detected = True
                self._finalize_month(last_month, last_value)
            elif target_month != last_month and value < 1.0:
                reset_detected = True
                self._finalize_month(last_month, last_value)
        
        if self.use_neon:
            try:
                # For historical records, use a timestamp from that month
                if month:
                    historical_date = datetime.strptime(f"{month}-01", "%Y-%m-%d")
                    record_timestamp = historical_date
                else:
                    record_timestamp = now

                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO groq_odometer_readings 
                            (timestamp, month, cumulative_value, is_reset, notes, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (record_timestamp, target_month, value, reset_detected, notes, now))
                        
                        # Update summary
                        self._update_monthly_summary_neon(cur, target_month, value)
                
                # Daily usage and reminder
                daily_usage = self._calculate_daily_usage(target_month, value) if not month else 0.0
                return {
                    "recorded": True, "month": target_month, "cumulative_value": value,
                    "reset_detected": reset_detected, "daily_usage_estimate": daily_usage,
                    "reminder_status": self.check_reminder_needs() if not month else {"status": "historical"},
                    "timestamp": record_timestamp.isoformat(), "historical_record": bool(month),
                    "source": "neon"
                }
            except Exception as e:
                logger.error(f"GroqOdometerTracker: Neon record_odometer_reading failed: {e}")
                raise

        # Fallback to SQLite
        with sqlite3.connect(self.db_path) as conn:
            if month:
                historical_date = datetime.strptime(f"{month}-01", "%Y-%m-%d")
                record_timestamp = historical_date.isoformat()
            else:
                record_timestamp = now.isoformat()
            
            conn.execute("""
                INSERT INTO groq_odometer_readings 
                (timestamp, month, cumulative_value, is_reset, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (record_timestamp, target_month, value, reset_detected, notes, now.isoformat()))
            self._update_monthly_summary_sqlite(conn, target_month, value)
        
        daily_usage = self._calculate_daily_usage(target_month, value) if not month else 0.0
        return {
            "recorded": True, "month": target_month, "cumulative_value": value,
            "reset_detected": reset_detected, "daily_usage_estimate": daily_usage,
            "reminder_status": self.check_reminder_needs() if not month else {"status": "historical"},
            "timestamp": record_timestamp if month else now.isoformat(), "historical_record": bool(month),
            "source": "sqlite"
        }
    
    def get_last_reading(self) -> Optional[Dict]:
        """Get the most recent odometer reading."""
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT timestamp, month, cumulative_value as value, is_final_reading as is_final, is_reset
                            FROM groq_odometer_readings
                            ORDER BY timestamp DESC
                            LIMIT 1
                        """)
                        row = cur.fetchone()
                        if row:
                            row['timestamp'] = row['timestamp'].isoformat()
                            return dict(row)
            except Exception as e:
                logger.error(f"GroqOdometerTracker: Neon get_last_reading failed: {e}")
                raise

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT timestamp, month, cumulative_value, is_final_reading, is_reset
                FROM groq_odometer_readings
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return {"timestamp": row[0], "month": row[1], "value": row[2], "is_final": row[3], "is_reset": row[4]}
        return None
    
    def _calculate_daily_usage(self, month: str, current_value: float) -> float:
        now = datetime.now()
        day_of_month = now.day
        if day_of_month > 0:
            return current_value / day_of_month
        return 0.0
    
    def _finalize_month(self, month: str, final_value: float):
        """Mark a month as finalized with its total cost."""
        now = datetime.now()
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE groq_odometer_readings SET is_final_reading = TRUE WHERE month = %s", (month,))
                        cur.execute("UPDATE groq_monthly_summaries SET total_cost = %s, finalized = TRUE, updated_at = %s WHERE month = %s", (final_value, now, month))
                return
            except Exception as e:
                logger.error(f"GroqOdometerTracker: Neon _finalize_month failed: {e}")
                raise

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE groq_odometer_readings SET is_final_reading = TRUE WHERE month = ?", (month,))
            conn.execute("UPDATE groq_monthly_summaries SET total_cost = ?, finalized = TRUE, updated_at = ? WHERE month = ?", (final_value, now.isoformat(), month))
    
    def _update_monthly_summary_neon(self, cur, month: str, value: float):
        now = datetime.now()
        cur.execute("SELECT month FROM groq_monthly_summaries WHERE month = %s", (month,))
        if cur.fetchone():
            cur.execute("UPDATE groq_monthly_summaries SET total_cost = %s, last_reading_date = %s, reading_count = reading_count + 1, updated_at = %s WHERE month = %s", (value, now.date(), now, month))
        else:
            cur.execute("INSERT INTO groq_monthly_summaries (month, total_cost, first_reading_date, last_reading_date, reading_count, created_at, updated_at) VALUES (%s, %s, %s, %s, 1, %s, %s)", (month, value, now.date(), now.date(), now, now))

    def _update_monthly_summary_sqlite(self, conn, month: str, value: float):
        now = datetime.now()
        cursor = conn.execute("SELECT month FROM groq_monthly_summaries WHERE month = ?", (month,))
        if cursor.fetchone():
            conn.execute("UPDATE groq_monthly_summaries SET total_cost = ?, last_reading_date = ?, reading_count = reading_count + 1, updated_at = ? WHERE month = ?", (value, now.date().isoformat(), now.isoformat(), month))
        else:
            conn.execute("INSERT INTO groq_monthly_summaries (month, total_cost, first_reading_date, last_reading_date, reading_count, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)", (month, value, now.date().isoformat(), now.date().isoformat(), now.isoformat(), now.isoformat()))
    
    def check_reminder_needs(self) -> Dict:
        """Check if we need to remind the user about readings."""
        now = datetime.now()
        status = OdometerStatus.NORMAL
        reminders_needed = []
        
        days_until_month_end = self._days_until_month_end()
        if days_until_month_end <= 3:
            status = OdometerStatus.APPROACHING_RESET
            reminders_needed.append({"type": "month_end", "urgency": "high" if days_until_month_end <= 1 else "medium", "message": f"📊 Groq usage reading needed in {days_until_month_end} days"})
        
        last_reading = self.get_last_reading()
        if last_reading:
            last_ts = datetime.fromisoformat(last_reading['timestamp'].replace('Z', '+00:00')) if isinstance(last_reading['timestamp'], str) else last_reading['timestamp']
            days_since = (now.astimezone() - last_ts.astimezone()).days if last_ts.tzinfo else (now - last_ts).days
            if days_since > 7:
                status = OdometerStatus.STALE
                reminders_needed.append({"type": "stale_data", "urgency": "low", "message": f"📈 Groq data is {days_since} days old"})
        else:
            status = OdometerStatus.NEEDS_READING
            reminders_needed.append({"type": "initial_reading", "urgency": "medium", "message": "🆕 No Groq data recorded yet"})
        
        if now.day <= 3:
            last_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            finalized = False
            if self.use_neon:
                try:
                    with psycopg2.connect(self.neon_url) as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT finalized FROM groq_monthly_summaries WHERE month = %s", (last_month,))
                            row = cur.fetchone()
                            if row: finalized = row[0]
                except Exception as e:
                    logger.error(f"GroqOdometerTracker: Neon check_reminder_needs failed: {e}")
            else:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("SELECT finalized FROM groq_monthly_summaries WHERE month = ?", (last_month,))
                    row = cursor.fetchone()
                    if row: finalized = row[0]
            
            if not finalized:
                reminders_needed.append({"type": "missed_month_end", "urgency": "high", "message": f"⚠️ Last month's Groq usage not recorded: {last_month}"})
        
        return {
            "status": status.value, "reminders": reminders_needed, "days_until_reset": days_until_month_end,
            "last_reading_age_days": days_since if last_reading else None
        }
    
    def _days_until_month_end(self) -> int:
        now = datetime.now()
        if now.month == 12: last_day = date(now.year + 1, 1, 1) - timedelta(days=1)
        else: last_day = date(now.year, now.month + 1, 1) - timedelta(days=1)
        return (last_day - now.date()).days
    
    def get_usage_for_virtual_budget(self) -> Dict:
        now = datetime.now()
        current_month = now.strftime("%Y-%m")
        
        if self.use_neon:
            try:
                with psycopg2.connect(self.neon_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT cumulative_value, timestamp FROM groq_odometer_readings WHERE month = %s ORDER BY timestamp DESC LIMIT 1", (current_month,))
                        curr = cur.fetchone()
                        if not curr: return {"has_data": False, "needs_reading": True}
                        
                        val, ts = curr[0], curr[1]
                        day = now.day
                        avg = val / day if day > 0 else 0
                        
                        yesterday = now - timedelta(days=1)
                        cur.execute("SELECT cumulative_value FROM groq_odometer_readings WHERE timestamp::date = %s ORDER BY timestamp DESC LIMIT 1", (yesterday.date(),))
                        yest = cur.fetchone()
                        diff = val - yest[0] if yest else 0
                        return {"has_data": True, "month": current_month, "cumulative_cost": val, "daily_average": avg, "daily_actual": diff if diff > 0 else avg, "day_of_month": day, "last_reading": ts.isoformat()}
            except Exception as e:
                logger.error(f"GroqOdometerTracker: Neon get_usage_for_virtual_budget failed: {e}")

        # Fallback only if neon not used or failed
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT cumulative_value, timestamp FROM groq_odometer_readings WHERE month = ? ORDER BY timestamp DESC LIMIT 1", (current_month,))
            curr = cursor.fetchone()
            if not curr: return {"has_data": False, "needs_reading": True}
            val, ts = curr[0], curr[1]
            day = now.day
            avg = val / day if day > 0 else 0
            yesterday = (now - timedelta(days=1)).isoformat()[:10]
            cursor = conn.execute("SELECT cumulative_value FROM groq_odometer_readings WHERE timestamp LIKE ? ORDER BY timestamp DESC LIMIT 1", (f"{yesterday}%",))
            yest = cursor.fetchone()
            diff = val - yest[0] if yest else 0
            return {"has_data": True, "month": current_month, "cumulative_cost": val, "daily_average": avg, "daily_actual": diff if diff > 0 else avg, "day_of_month": day, "last_reading": ts}
    
    def generate_narrator_context(self) -> Dict:
        reminder_status = self.check_reminder_needs()
        usage_data = self.get_usage_for_virtual_budget()
        context = {
            "groq_tracking": {
                "status": reminder_status["status"], "has_current_data": usage_data.get("has_data", False),
                "days_until_reset": reminder_status["days_until_reset"], "needs_action": len(reminder_status["reminders"]) > 0
            }
        }
        if reminder_status["reminders"]:
            urgent = [r for r in reminder_status["reminders"] if r["urgency"] == "high"]
            if urgent: context["groq_tracking"]["urgent_reminder"] = urgent[0]["message"]
        if usage_data.get("has_data"):
            context["groq_tracking"]["current_month_spend"] = usage_data["cumulative_cost"]
            context["groq_tracking"]["daily_average"] = usage_data["daily_average"]
        return context

_global_tracker = None
def _get_tracker() -> GroqOdometerTracker:
    global _global_tracker
    if _global_tracker is None: _global_tracker = GroqOdometerTracker()
    return _global_tracker

def record_groq_reading(value: float, notes: str = "", month: Optional[str] = None) -> Dict:
    return _get_tracker().record_odometer_reading(value, notes, month)

def get_groq_reminder_status() -> Dict:
    return _get_tracker().check_reminder_needs()

def get_groq_context_for_narrator() -> Dict:
    return _get_tracker().generate_narrator_context()

if __name__ == "__main__":
    vbm = GroqOdometerTracker()
    print("=== Groq Odometer Status ===")
    print(json.dumps(vbm.check_reminder_needs(), indent=2))
