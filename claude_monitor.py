"""
Claude Credit Monitor - Real-time budget tracking for Mecris
Tracks API usage, burn rate, and sends alerts when credits run low
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

import httpx
from dotenv import load_dotenv

from twilio_sender import send_sms

load_dotenv()
logger = logging.getLogger("mecris.claude_monitor")

@dataclass
class CreditUsage:
    """Credit usage tracking data"""
    timestamp: datetime
    credits_used: float
    credits_remaining: float
    session_cost: float
    daily_burn: float
    days_remaining: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "credits_used": self.credits_used,
            "credits_remaining": self.credits_remaining,
            "session_cost": self.session_cost,
            "daily_burn": self.daily_burn,
            "days_remaining": self.days_remaining
        }

@dataclass
class BudgetAlert:
    """Budget alert configuration"""
    level: str  # "critical", "warning", "info"
    threshold_days: float
    message: str
    sent: bool = False

class ClaudeMonitor:
    """Monitor Claude API usage and budget"""
    
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.usage_file = os.getenv("CLAUDE_USAGE_FILE", "claude_usage.json")
        self.budget_limit = float(os.getenv("CLAUDE_BUDGET_LIMIT", "25.00"))
        self.expiry_date = os.getenv("CLAUDE_EXPIRY_DATE", "2025-08-05")  # YYYY-MM-DD
        
        # Alert thresholds (days remaining)
        self.alerts = [
            BudgetAlert("critical", 1.0, "🚨 CRITICAL: <1 day of Claude credits left"),
            BudgetAlert("warning", 2.0, "⚠️ WARNING: <2 days of Claude credits left"),
            BudgetAlert("info", 5.0, "📊 INFO: <5 days of Claude credits left")
        ]
        
        # HTTP client for Anthropic API
        self.client = httpx.AsyncClient(timeout=10.0)
        
    async def health_check(self) -> str:
        """Check if Claude Monitor is functioning"""
        try:
            if not self.api_key:
                return "not_configured"
            
            # Try to load usage data
            usage = await self.get_current_usage()
            return "ok" if usage else "error"
            
        except Exception as e:
            logger.warning(f"Claude Monitor health check failed: {e}")
            return "error"
    
    async def _load_usage_history(self) -> List[Dict[str, Any]]:
        """Load usage history from local file"""
        try:
            if os.path.exists(self.usage_file):
                with open(self.usage_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Failed to load usage history: {e}")
            return []
    
    async def _save_usage_history(self, history: List[Dict[str, Any]]) -> bool:
        """Save usage history to local file"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(history, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save usage history: {e}")
            return False
    
    def _calculate_daily_burn(self, history: List[Dict[str, Any]]) -> float:
        """Calculate daily burn rate from usage history"""
        if len(history) < 2:
            return 0.0
        
        # Look at last 7 days of data
        recent_history = history[-7:] if len(history) >= 7 else history
        
        if len(recent_history) < 2:
            return 0.0
        
        try:
            # Calculate total spend over the period
            first_entry = recent_history[0]
            last_entry = recent_history[-1]
            
            first_time = datetime.fromisoformat(first_entry["timestamp"])
            last_time = datetime.fromisoformat(last_entry["timestamp"])
            
            time_diff = (last_time - first_time).total_seconds() / 86400  # days
            
            if time_diff <= 0:
                return 0.0
            
            credit_diff = first_entry["credits_remaining"] - last_entry["credits_remaining"]
            daily_burn = credit_diff / time_diff
            
            return max(0.0, daily_burn)
            
        except Exception as e:
            logger.error(f"Failed to calculate daily burn: {e}")
            return 0.0
    
    def _days_until_expiry(self) -> float:
        """Calculate days until credit expiry"""
        try:
            expiry = datetime.strptime(self.expiry_date, "%Y-%m-%d")
            now = datetime.now()
            return max(0.0, (expiry - now).total_seconds() / 86400)
        except Exception as e:
            logger.error(f"Failed to calculate expiry days: {e}")
            return 0.0
    
    async def get_current_usage(self) -> Optional[CreditUsage]:
        """Get current credit usage status"""
        try:
            # Load historical data
            history = await self._load_usage_history()
            
            # For now, we'll simulate API usage tracking
            # In production, this would call Anthropic's usage API
            # Since that API doesn't exist yet, we track manually
            
            if not history:
                # Initialize with budget limit
                current_usage = CreditUsage(
                    timestamp=datetime.now(),
                    credits_used=0.0,
                    credits_remaining=self.budget_limit,
                    session_cost=0.0,
                    daily_burn=0.0,
                    days_remaining=self._days_until_expiry()
                )
            else:
                last_entry = history[-1]
                daily_burn = self._calculate_daily_burn(history)
                remaining = last_entry["credits_remaining"]
                days_remaining = min(
                    self._days_until_expiry(),
                    remaining / daily_burn if daily_burn > 0 else float('inf')
                )
                
                current_usage = CreditUsage(
                    timestamp=datetime.now(),
                    credits_used=self.budget_limit - remaining,
                    credits_remaining=remaining,
                    session_cost=0.0,  # Would track current session
                    daily_burn=daily_burn,
                    days_remaining=days_remaining
                )
            
            return current_usage
            
        except Exception as e:
            logger.error(f"Failed to get current usage: {e}")
            return None
    
    async def record_usage(self, session_cost: float, description: str = "") -> bool:
        """Record new usage session"""
        try:
            history = await self._load_usage_history()
            current = await self.get_current_usage()
            
            if not current:
                return False
            
            # Update usage
            new_remaining = current.credits_remaining - session_cost
            new_used = current.credits_used + session_cost
            
            usage_entry = CreditUsage(
                timestamp=datetime.now(),
                credits_used=new_used,
                credits_remaining=new_remaining,
                session_cost=session_cost,
                daily_burn=self._calculate_daily_burn(history) if history else 0.0,
                days_remaining=min(
                    self._days_until_expiry(),
                    new_remaining / self._calculate_daily_burn(history) if self._calculate_daily_burn(history) > 0 else float('inf')
                )
            )
            
            # Add metadata
            usage_dict = usage_entry.to_dict()
            usage_dict["description"] = description
            
            history.append(usage_dict)
            
            # Keep only last 30 days
            cutoff_date = datetime.now() - timedelta(days=30)
            history = [
                entry for entry in history 
                if datetime.fromisoformat(entry["timestamp"]) > cutoff_date
            ]
            
            success = await self._save_usage_history(history)
            
            if success:
                # Check for alerts
                await self._check_budget_alerts(usage_entry)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to record usage: {e}")
            return False
    
    async def _check_budget_alerts(self, usage: CreditUsage) -> None:
        """Check if budget alerts should be sent"""
        try:
            for alert in self.alerts:
                if usage.days_remaining <= alert.threshold_days and not alert.sent:
                    # Send alert
                    detailed_message = f"""{alert.message}

${usage.credits_remaining:.2f} remaining
${usage.daily_burn:.2f}/day burn rate
~{usage.days_remaining:.1f} days left

Expiry: {self.expiry_date}"""
                    
                    success = send_sms(detailed_message)
                    if success:
                        alert.sent = True
                        logger.info(f"Budget alert sent: {alert.level}")
                    
        except Exception as e:
            logger.error(f"Failed to check budget alerts: {e}")
    
    async def get_usage_summary(self) -> Dict[str, Any]:
        """Get formatted usage summary for narrator context"""
        try:
            current = await self.get_current_usage()
            if not current:
                return {"error": "Unable to load usage data"}
            
            # Determine status
            if current.days_remaining <= 1:
                status = "🚨 CRITICAL"
            elif current.days_remaining <= 2:
                status = "⚠️ WARNING"
            elif current.days_remaining <= 5:
                status = "⏰ CAUTION"
            else:
                status = "✅ HEALTHY"
            
            return {
                "status": status,
                "credits_remaining": current.credits_remaining,
                "credits_used": current.credits_used,
                "daily_burn": current.daily_burn,
                "days_remaining": current.days_remaining,
                "expiry_date": self.expiry_date,
                "budget_limit": self.budget_limit,
                "utilization_pct": (current.credits_used / self.budget_limit) * 100,
                "last_updated": current.timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get usage summary: {e}")
            return {"error": str(e)}
    
    async def simulate_usage_update(self, cost: float) -> Dict[str, Any]:
        """Simulate recording usage (for testing/manual updates)"""
        success = await self.record_usage(cost, "Manual update")
        if success:
            return await self.get_usage_summary()
        else:
            return {"error": "Failed to record usage"}
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Convenience functions for manual usage tracking
async def track_session_cost(cost: float, description: str = ""):
    """Track cost of current session"""
    monitor = ClaudeMonitor()
    try:
        return await monitor.record_usage(cost, description)
    finally:
        await monitor.close()

async def get_budget_status():
    """Get current budget status"""
    monitor = ClaudeMonitor()
    try:
        return await monitor.get_usage_summary()
    finally:
        await monitor.close()

if __name__ == "__main__":
    import asyncio
    
    async def test_monitor():
        monitor = ClaudeMonitor()
        try:
            print("=== Claude Monitor Test ===")
            
            # Test health check
            health = await monitor.health_check()
            print(f"Health: {health}")
            
            # Test current usage
            usage = await monitor.get_current_usage()
            if usage:
                print(f"Credits remaining: ${usage.credits_remaining:.2f}")
                print(f"Daily burn: ${usage.daily_burn:.2f}")
                print(f"Days remaining: {usage.days_remaining:.1f}")
            
            # Test usage summary
            summary = await monitor.get_usage_summary()
            print("\nUsage Summary:")
            for key, value in summary.items():
                print(f"  {key}: {value}")
            
        finally:
            await monitor.close()
    
    asyncio.run(test_monitor())