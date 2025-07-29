"""
Beeminder API Client - Goal tracking and derailment detection
Handles Beeminder API calls and beemergency logic
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("mecris.beeminder")

@dataclass
class BeeminderGoal:
    """Structured representation of a Beeminder goal"""
    slug: str
    title: str
    current_value: float
    target_value: float
    safebuf: int  # Days until derailment
    deadline: datetime
    derail_risk: str  # "CRITICAL" | "WARNING" | "CAUTION" | "SAFE"
    pledge: float
    rate: float
    runits: str  # Rate units (e.g., "d" for daily)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "safebuf": self.safebuf,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "derail_risk": self.derail_risk,
            "pledge": self.pledge,
            "rate": self.rate,
            "runits": self.runits
        }

@dataclass
class BeemergencyAlert:
    """Alert for goals requiring immediate attention"""
    goal_slug: str
    message: str
    urgency: str  # "IMMEDIATE" | "TODAY" | "SOON"
    suggested_action: str
    time_remaining: str

class BeeminderClient:
    """Client for Beeminder API with derailment detection"""
    
    def __init__(self):
        self.username = os.getenv("BEEMINDER_USERNAME")
        self.auth_token = os.getenv("BEEMINDER_AUTH_TOKEN")
        self.base_url = os.getenv("BEEMINDER_API_BASE", "https://www.beeminder.com/api/v1")
        
        if not self.username or not self.auth_token:
            logger.warning("Beeminder credentials not configured")
        
        # HTTP client with timeout
        self.client = httpx.AsyncClient(timeout=15.0)
    
    async def health_check(self) -> str:
        """Check if Beeminder API is accessible"""
        if not self.username or not self.auth_token:
            return "not_configured"
        
        try:
            response = await self.client.get(
                f"{self.base_url}/users/{self.username}.json",
                params={"auth_token": self.auth_token}
            )
            return "ok" if response.status_code == 200 else "error"
        except Exception as e:
            logger.warning(f"Beeminder health check failed: {e}")
            return "unreachable"
    
    async def _api_call(self, endpoint: str, method: str = "GET", data: Dict = None) -> Optional[Dict]:
        """Make authenticated API call to Beeminder"""
        if not self.username or not self.auth_token:
            logger.error("Beeminder credentials not configured")
            return None
        
        url = f"{self.base_url}/{endpoint}"
        params = {"auth_token": self.auth_token}
        
        try:
            if method == "GET":
                response = await self.client.get(url, params=params)
            elif method == "POST":
                response = await self.client.post(url, params=params, json=data or {})
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                return None
            
            if response.status_code != 200:
                logger.error(f"Beeminder API call failed: {response.status_code} - {response.text}")
                return None
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Beeminder API call to {endpoint} failed: {e}")
            return None
    
    async def get_user_goals(self) -> List[Dict[str, Any]]:
        """Get all goals for the authenticated user"""
        result = await self._api_call(f"users/{self.username}/goals.json")
        return result if result else []
    
    async def get_goal_details(self, goal_slug: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for specific goal"""
        return await self._api_call(f"users/{self.username}/goals/{goal_slug}.json")
    
    async def add_datapoint(self, goal_slug: str, value: float, comment: str = "") -> bool:
        """Add a datapoint to a goal"""
        data = {
            "value": value,
            "comment": comment,
            "timestamp": int(datetime.now().timestamp())
        }
        
        result = await self._api_call(
            f"users/{self.username}/goals/{goal_slug}/datapoints.json",
            method="POST",
            data=data
        )
        
        return result is not None
    
    def _classify_derail_risk(self, safebuf: int) -> str:
        """Classify derailment risk based on safebuf days"""
        if safebuf <= 0:
            return "CRITICAL"    # Derailing today/already derailed
        elif safebuf == 1:
            return "WARNING"     # Derails tomorrow
        elif safebuf <= 3:
            return "CAUTION"     # Derails within 3 days
        else:
            return "SAFE"
    
    def _calculate_deadline(self, safebuf: int) -> datetime:
        """Calculate deadline based on safebuf"""
        return datetime.now() + timedelta(days=safebuf)
    
    def _parse_goal(self, goal_data: Dict[str, Any]) -> BeeminderGoal:
        """Parse raw API response into structured BeeminderGoal"""
        safebuf = goal_data.get("safebuf", 0)
        
        return BeeminderGoal(
            slug=goal_data.get("slug", ""),
            title=goal_data.get("title", goal_data.get("slug", "")),
            current_value=float(goal_data.get("curval", 0)),
            target_value=float(goal_data.get("goalval", 0)),
            safebuf=safebuf,
            deadline=self._calculate_deadline(safebuf),
            derail_risk=self._classify_derail_risk(safebuf),
            pledge=float(goal_data.get("pledge", 0)),
            rate=float(goal_data.get("rate", 0)),
            runits=goal_data.get("runits", "d")
        )
    
    async def get_all_goals(self) -> List[Dict[str, Any]]:
        """Get all goals with structured data and risk assessment"""
        raw_goals = await self.get_user_goals()
        
        structured_goals = []
        for goal_data in raw_goals:
            try:
                goal = self._parse_goal(goal_data)
                structured_goals.append(goal.to_dict())
            except Exception as e:
                logger.error(f"Failed to parse goal {goal_data.get('slug', 'unknown')}: {e}")
                continue
        
        return structured_goals
    
    async def get_emergencies(self) -> List[Dict[str, Any]]:
        """Get goals requiring immediate attention (beemergencies)"""
        all_goals = await self.get_all_goals()
        emergencies = []
        
        for goal in all_goals:
            risk = goal.get("derail_risk", "SAFE")
            safebuf = goal.get("safebuf", 999)
            slug = goal.get("slug", "")
            
            if risk in ["CRITICAL", "WARNING", "CAUTION"]:
                # Determine urgency and message
                if risk == "CRITICAL":
                    urgency = "IMMEDIATE"
                    if safebuf <= 0:
                        message = f"DERAILING NOW! Need data immediately"
                        time_remaining = "0 hours"
                    else:
                        message = f"Derails in {safebuf} day(s)"
                        time_remaining = f"{safebuf * 24} hours"
                        
                elif risk == "WARNING":
                    urgency = "TODAY"
                    message = f"Derails tomorrow - act today"
                    time_remaining = "24 hours"
                    
                else:  # CAUTION
                    urgency = "SOON"
                    message = f"Derails in {safebuf} days"
                    time_remaining = f"{safebuf} days"
                
                # Generate suggested action
                rate = goal.get("rate", 0)
                runits = goal.get("runits", "d")
                current = goal.get("current_value", 0)
                target = goal.get("target_value", 0)
                
                needed = max(0, target - current)
                suggested_action = f"Add {needed:.1f} units" if needed > 0 else "Data entry required"
                
                emergencies.append({
                    "goal_slug": slug,
                    "message": message,
                    "urgency": urgency,
                    "suggested_action": suggested_action,
                    "time_remaining": time_remaining,
                    "safebuf": safebuf,
                    "derail_risk": risk,
                    "pledge": goal.get("pledge", 0)
                })
        
        # Sort by urgency (most critical first)
        urgency_order = {"IMMEDIATE": 0, "TODAY": 1, "SOON": 2}
        emergencies.sort(key=lambda x: (urgency_order.get(x["urgency"], 3), x["safebuf"]))
        
        return emergencies
    
    async def get_critical_goals(self) -> List[Dict[str, Any]]:
        """Get only goals in CRITICAL state (derailing today/already derailed)"""
        emergencies = await self.get_emergencies()
        return [e for e in emergencies if e["urgency"] == "IMMEDIATE"]
    
    async def format_emergency_summary(self) -> str:
        """Format emergency summary for narrator context"""
        emergencies = await self.get_emergencies()
        
        if not emergencies:
            return "✅ All Beeminder goals are safe"
        
        critical = [e for e in emergencies if e["urgency"] == "IMMEDIATE"]
        warning = [e for e in emergencies if e["urgency"] == "TODAY"]
        caution = [e for e in emergencies if e["urgency"] == "SOON"]
        
        summary = []
        
        if critical:
            summary.append(f"🚨 {len(critical)} CRITICAL: {', '.join([e['goal_slug'] for e in critical])}")
        
        if warning:
            summary.append(f"⚠️ {len(warning)} WARNING: {', '.join([e['goal_slug'] for e in warning])}")
        
        if caution:
            summary.append(f"⏰ {len(caution)} CAUTION: {', '.join([e['goal_slug'] for e in caution])}")
        
        return " | ".join(summary)
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()