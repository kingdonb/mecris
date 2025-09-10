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
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """Initialize odometer tracking tables."""
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
                    reminder_type TEXT NOT NULL,  -- 'month_end', 'stale_data', 'reset_detected'
                    scheduled_for DATE NOT NULL,
                    sent BOOLEAN DEFAULT FALSE,
                    sent_at TEXT,
                    response TEXT,
                    created_at TEXT NOT NULL
                )
            """)
    
    def record_odometer_reading(self, value: float, notes: str = "") -> Dict:
        """
        Record a new odometer reading, handling month boundaries intelligently.
        
        Args:
            value: Current cumulative cost shown in Groq console
            notes: Optional notes about the reading
            
        Returns:
            Dict with recording status and derived daily costs
        """
        now = datetime.now()
        current_month = now.strftime("%Y-%m")
        
        # Check for odometer reset
        last_reading = self.get_last_reading()
        reset_detected = False
        
        if last_reading:
            last_month = last_reading['month']
            last_value = last_reading['value']
            
            # Detect reset: new value < old value OR month changed
            if value < last_value and current_month != last_month:
                reset_detected = True
                # Finalize the previous month
                self._finalize_month(last_month, last_value)
            elif current_month != last_month and value < 1.0:
                # Month changed and value is near zero - likely a reset
                reset_detected = True
                self._finalize_month(last_month, last_value)
        
        # Record the reading
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO groq_odometer_readings 
                (timestamp, month, cumulative_value, is_reset, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                now.isoformat(),
                current_month,
                value,
                reset_detected,
                notes,
                now.isoformat()
            ))
            
            # Update monthly summary
            self._update_monthly_summary(current_month, value)
        
        # Calculate derived daily usage
        daily_usage = self._calculate_daily_usage(current_month, value)
        
        # Check if we need reminders
        reminder_status = self.check_reminder_needs()
        
        return {
            "recorded": True,
            "month": current_month,
            "cumulative_value": value,
            "reset_detected": reset_detected,
            "daily_usage_estimate": daily_usage,
            "reminder_status": reminder_status,
            "timestamp": now.isoformat()
        }
    
    def get_last_reading(self) -> Optional[Dict]:
        """Get the most recent odometer reading."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT timestamp, month, cumulative_value, is_final_reading, is_reset
                FROM groq_odometer_readings
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if row:
                return {
                    "timestamp": row[0],
                    "month": row[1],
                    "value": row[2],
                    "is_final": row[3],
                    "is_reset": row[4]
                }
        return None
    
    def _calculate_daily_usage(self, month: str, current_value: float) -> float:
        """Calculate estimated daily usage from cumulative monthly value."""
        # Get day of month
        now = datetime.now()
        day_of_month = now.day
        
        # Simple average for the month so far
        if day_of_month > 0:
            return current_value / day_of_month
        return 0.0
    
    def _finalize_month(self, month: str, final_value: float):
        """Mark a month as finalized with its total cost."""
        with sqlite3.connect(self.db_path) as conn:
            # Mark the last reading as final
            conn.execute("""
                UPDATE groq_odometer_readings
                SET is_final_reading = TRUE
                WHERE month = ? 
                ORDER BY timestamp DESC
                LIMIT 1
            """, (month,))
            
            # Finalize the monthly summary
            conn.execute("""
                UPDATE groq_monthly_summaries
                SET total_cost = ?, finalized = TRUE, updated_at = ?
                WHERE month = ?
            """, (final_value, datetime.now().isoformat(), month))
    
    def _update_monthly_summary(self, month: str, value: float):
        """Update or create monthly summary."""
        now = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            # Check if summary exists
            cursor = conn.execute("""
                SELECT month FROM groq_monthly_summaries WHERE month = ?
            """, (month,))
            
            if cursor.fetchone():
                # Update existing
                conn.execute("""
                    UPDATE groq_monthly_summaries
                    SET total_cost = ?, 
                        last_reading_date = ?,
                        reading_count = reading_count + 1,
                        updated_at = ?
                    WHERE month = ?
                """, (value, now.date().isoformat(), now.isoformat(), month))
            else:
                # Create new
                conn.execute("""
                    INSERT INTO groq_monthly_summaries
                    (month, total_cost, first_reading_date, last_reading_date, 
                     reading_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (month, value, now.date().isoformat(), now.date().isoformat(),
                      now.isoformat(), now.isoformat()))
    
    def check_reminder_needs(self) -> Dict:
        """
        Check if we need to remind the user about readings.
        
        Returns status and urgency of reminders needed.
        """
        now = datetime.now()
        status = OdometerStatus.NORMAL
        reminders_needed = []
        
        # Check 1: Are we approaching month end? (last 3 days)
        days_until_month_end = self._days_until_month_end()
        if days_until_month_end <= 3:
            status = OdometerStatus.APPROACHING_RESET
            reminders_needed.append({
                "type": "month_end",
                "urgency": "high" if days_until_month_end <= 1 else "medium",
                "message": f"📊 Groq usage reading needed in {days_until_month_end} days before month reset"
            })
        
        # Check 2: Is our data stale? (>7 days old)
        last_reading = self.get_last_reading()
        if last_reading:
            last_timestamp = datetime.fromisoformat(last_reading['timestamp'])
            days_since_reading = (now - last_timestamp).days
            
            if days_since_reading > 7:
                status = OdometerStatus.STALE
                reminders_needed.append({
                    "type": "stale_data",
                    "urgency": "low",
                    "message": f"📈 Groq data is {days_since_reading} days old - consider updating"
                })
        else:
            # No readings at all
            status = OdometerStatus.NEEDS_READING
            reminders_needed.append({
                "type": "initial_reading",
                "urgency": "medium",
                "message": "🆕 No Groq usage data recorded yet - initial reading needed"
            })
        
        # Check 3: Did we miss the month-end reading?
        if now.day <= 3:  # First 3 days of new month
            current_month = now.strftime("%Y-%m")
            last_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT finalized FROM groq_monthly_summaries WHERE month = ?
                """, (last_month,))
                
                row = cursor.fetchone()
                if not row or not row[0]:
                    reminders_needed.append({
                        "type": "missed_month_end",
                        "urgency": "high",
                        "message": f"⚠️ Last month's Groq usage not recorded - please input final {last_month} value"
                    })
        
        return {
            "status": status.value,
            "reminders": reminders_needed,
            "days_until_reset": days_until_month_end,
            "last_reading_age_days": (now - datetime.fromisoformat(last_reading['timestamp'])).days if last_reading else None
        }
    
    def _days_until_month_end(self) -> int:
        """Calculate days until the end of current month."""
        now = datetime.now()
        
        # Get last day of current month
        if now.month == 12:
            last_day = date(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(now.year, now.month + 1, 1) - timedelta(days=1)
        
        return (last_day - now.date()).days
    
    def get_usage_for_virtual_budget(self) -> Dict:
        """
        Get Groq usage data formatted for virtual budget system.
        
        Calculates daily usage from odometer readings and handles
        month boundaries intelligently.
        """
        now = datetime.now()
        current_month = now.strftime("%Y-%m")
        
        # Get current month's readings
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT cumulative_value, timestamp
                FROM groq_odometer_readings
                WHERE month = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (current_month,))
            
            current_reading = cursor.fetchone()
            
            if not current_reading:
                # No data for current month
                return {
                    "has_data": False,
                    "needs_reading": True,
                    "message": "No Groq usage data for current month"
                }
            
            current_value = current_reading[0]
            
            # Calculate daily average
            day_of_month = now.day
            daily_average = current_value / day_of_month if day_of_month > 0 else 0
            
            # Get yesterday's value for daily difference
            yesterday = now - timedelta(days=1)
            cursor = conn.execute("""
                SELECT cumulative_value
                FROM groq_odometer_readings
                WHERE DATE(timestamp) = DATE(?)
                ORDER BY timestamp DESC
                LIMIT 1
            """, (yesterday.isoformat(),))
            
            yesterday_reading = cursor.fetchone()
            daily_difference = 0
            
            if yesterday_reading:
                # We have yesterday's data - calculate actual daily usage
                daily_difference = current_value - yesterday_reading[0]
            
            return {
                "has_data": True,
                "month": current_month,
                "cumulative_cost": current_value,
                "daily_average": daily_average,
                "daily_actual": daily_difference if daily_difference > 0 else daily_average,
                "day_of_month": day_of_month,
                "last_reading": current_reading[1]
            }
    
    def generate_narrator_context(self) -> Dict:
        """
        Generate context for the narrator to use in conversations.
        
        This is what gets integrated into CLAUDE.md for proactive reminders.
        """
        reminder_status = self.check_reminder_needs()
        usage_data = self.get_usage_for_virtual_budget()
        
        context = {
            "groq_tracking": {
                "status": reminder_status["status"],
                "has_current_data": usage_data.get("has_data", False),
                "days_until_reset": reminder_status["days_until_reset"],
                "needs_action": len(reminder_status["reminders"]) > 0
            }
        }
        
        # Add urgent reminders to context
        if reminder_status["reminders"]:
            urgent = [r for r in reminder_status["reminders"] if r["urgency"] == "high"]
            if urgent:
                context["groq_tracking"]["urgent_reminder"] = urgent[0]["message"]
        
        # Add usage summary if we have data
        if usage_data.get("has_data"):
            context["groq_tracking"]["current_month_spend"] = usage_data["cumulative_cost"]
            context["groq_tracking"]["daily_average"] = usage_data["daily_average"]
        
        return context

# Global singleton instance to prevent connection leaks
_global_tracker = None

def _get_tracker() -> GroqOdometerTracker:
    """Get singleton tracker instance to prevent connection leaks."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = GroqOdometerTracker()
    return _global_tracker

# Convenience functions for integration
def record_groq_reading(value: float, notes: str = "") -> Dict:
    """Record a Groq odometer reading."""
    tracker = _get_tracker()
    return tracker.record_odometer_reading(value, notes)

def get_groq_reminder_status() -> Dict:
    """Check if Groq readings are needed."""
    tracker = _get_tracker()
    return tracker.check_reminder_needs()

def get_groq_context_for_narrator() -> Dict:
    """Get Groq context for narrator integration."""
    tracker = _get_tracker()
    return tracker.generate_narrator_context()

if __name__ == "__main__":
    # Test the odometer system
    tracker = GroqOdometerTracker()
    
    print("=== Groq Odometer Tracker Test ===")
    
    # Simulate some readings
    test_reading = tracker.record_odometer_reading(1.06, "Current month usage from console")
    print(f"Recorded: ${test_reading['cumulative_value']:.2f}")
    print(f"Daily estimate: ${test_reading['daily_usage_estimate']:.4f}")
    
    # Check reminders
    reminders = tracker.check_reminder_needs()
    print(f"\nReminder status: {reminders['status']}")
    print(f"Days until reset: {reminders['days_until_reset']}")
    
    for reminder in reminders['reminders']:
        print(f"  {reminder['urgency'].upper()}: {reminder['message']}")
    
    # Get narrator context
    context = tracker.generate_narrator_context()
    print(f"\nNarrator context: {json.dumps(context, indent=2)}")