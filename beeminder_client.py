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

class BeeminderAPIError(Exception):
    """Custom exception for Beeminder API errors."""
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code

from services.encryption_service import EncryptionService

class BeeminderClient:
    """Client for Beeminder API with derailment detection"""
    
    def __init__(self, user_id: str = None):
        self.user_id = user_id
        self.username = None
        self.auth_token = None
        self.base_url = os.getenv("BEEMINDER_API_BASE", "https://www.beeminder.com/api/v1")
        self.encryption = EncryptionService()
        
        # HTTP client with timeout
        self.client = httpx.AsyncClient(timeout=15.0)

    async def _load_credentials(self):
        """Fetch and decrypt credentials from Neon."""
        # Avoid circular import
        from usage_tracker import UsageTracker
        tracker = UsageTracker()
        target_user_id = tracker.resolve_user_id(self.user_id)
        neon_url = os.getenv("NEON_DB_URL")
        
        if not neon_url:
            self.username = os.getenv("BEEMINDER_USERNAME")
            self.auth_token = os.getenv("BEEMINDER_AUTH_TOKEN")
            if self.username and self.auth_token:
                logger.warning(f"Using legacy BEEMINDER_USERNAME env var for user {target_user_id}")
                return
            raise RuntimeError("NEON_DB_URL not set and legacy env vars missing")

        try:
            import psycopg2
            with psycopg2.connect(neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT beeminder_user, beeminder_token_encrypted FROM users WHERE pocket_id_sub = %s",
                        (target_user_id,)
                    )
                    row = cur.fetchone()
                    if row and row[0] and row[1]:
                        self.username = row[0]
                        self.auth_token = self.encryption.decrypt(row[1])
                        logger.info(f"Loaded encrypted Beeminder credentials for user {target_user_id}")
                    else:
                        # Final fallback to env
                        self.username = os.getenv("BEEMINDER_USERNAME")
                        self.auth_token = os.getenv("BEEMINDER_AUTH_TOKEN")
                        if not (self.username and self.auth_token):
                            raise RuntimeError(f"No Beeminder credentials found in DB or ENV for user {target_user_id}")
                        logger.warning(f"Falling back to legacy env vars for user {target_user_id}")
        except Exception as e:
            logger.error(f"Failed to load Beeminder credentials: {e}")
            raise

    async def health_check(self) -> str:
        """Check if Beeminder API is accessible"""
        if not self.username or not self.auth_token:
            try:
                await self._load_credentials()
            except Exception:
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
            await self._load_credentials()
            
        url = f"{self.base_url}/{endpoint}"
        params = {"auth_token": self.auth_token}
        
        try:
            if method == "GET":
                response = await self.client.get(url, params=params)
            elif method == "POST":
                response = await self.client.post(url, params=params, json=data or {})
            else:
                raise BeeminderAPIError(f"Unsupported HTTP method: {method}", status_code=400)
            
            if response.status_code != 200:
                msg = f"Beeminder API call failed: {response.status_code} - {response.text}"
                logger.error(msg)
                raise BeeminderAPIError(msg, status_code=response.status_code)
            
            return response.json()
            
        except httpx.RequestError as e:
            msg = f"Beeminder API call to {endpoint} failed: {e}"
            logger.error(msg)
            raise BeeminderAPIError(msg) from e
    
    async def get_user_goals(self) -> List[Dict[str, Any]]:
        """Get all goals for the authenticated user"""
        try:
            result = await self._api_call(f"users/{self.username}/goals.json")
            return result if result else []
        except BeeminderAPIError:
            return []
    
    async def get_goal_details(self, goal_slug: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for specific goal"""
        return await self._api_call(f"users/{self.username}/goals/{goal_slug}.json")
    
    async def get_goal_datapoints(self, goal_slug: str, since: Optional[datetime] = None, count: int = 7) -> List[Dict[str, Any]]:
        """Get recent datapoints for a goal
        
        Args:
            goal_slug: The goal to fetch datapoints for
            since: Only return datapoints after this timestamp
            count: Maximum number of datapoints to return (default: 7)
        """
        endpoint = f"users/{self.username}/goals/{goal_slug}/datapoints.json"
        
        # Build query string manually since _api_call handles auth params
        query_params = [f"count={count}"]
        if since:
            query_params.append(f"since={int(since.timestamp())}")
        
        if query_params:
            endpoint += "?" + "&".join(query_params)
        
        result = await self._api_call(endpoint)
        return result if result else []
    
    async def has_activity_today(self, goal_slug: str = "bike") -> bool:
        """Check if any datapoints were added today to the specified goal
        
        This is the core method for detecting daily activity without parallel tracking.
        Returns True if any datapoint was created today (after midnight US/Eastern).
        """
        import zoneinfo
        eastern = zoneinfo.ZoneInfo("US/Eastern")
        now_eastern = datetime.now(eastern)
        today_start_eastern = now_eastern.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Beeminder 'since' parameter expects a Unix timestamp
        # We want everything since local midnight
        datapoints = await self.get_goal_datapoints(goal_slug, since=today_start_eastern, count=10)
        
        # Check if any datapoints have today's timestamp in Eastern time
        today_date = today_start_eastern.date()
        for datapoint in datapoints:
            # Beeminder timestamps are Unix timestamps (seconds since epoch)
            dp_timestamp = datapoint.get("timestamp", 0)
            if dp_timestamp:
                # Convert Unix timestamp to Eastern time for comparison
                dp_dt_eastern = datetime.fromtimestamp(dp_timestamp, tz=zoneinfo.ZoneInfo("UTC")).astimezone(eastern)
                if dp_dt_eastern.date() == today_date:
                    logger.info(f"Activity detected for {goal_slug}: datapoint at {dp_dt_eastern}")
                    return True
        
        logger.info(f"No activity today for {goal_slug} (Local day: {today_date})")
        return False
    
    async def get_daily_activity_status(self, goal_slug: str = "bike") -> Dict[str, Any]:
        """Get comprehensive daily activity status for narrator context"""
        try:
            has_activity = await self.has_activity_today(goal_slug)
            return {
                "goal_slug": goal_slug,
                "has_activity_today": has_activity,
                "status": "completed" if has_activity else "needed",
                "check_time": datetime.now().isoformat(),
                "message": f"✅ Walk logged today" if has_activity else "🚶‍♂️ No walk detected today"
            }
        except BeeminderAPIError as e:
            if e.status_code == 404:
                return {
                    "goal_slug": goal_slug,
                    "has_activity_today": False,
                    "status": "error",
                    "check_time": datetime.now().isoformat(),
                    "message": "Goal not found"
                }
            else:
                return {
                    "goal_slug": goal_slug,
                    "has_activity_today": False,
                    "status": "error",
                    "check_time": datetime.now().isoformat(),
                    "message": f"API Error: {str(e)}"
                }
    
    async def add_datapoint(self, goal_slug: str, value: float, comment: str = "", requestid: Optional[str] = None) -> bool:
        """Add a datapoint to a goal"""
        data = {
            "value": value,
            "comment": comment,
            "timestamp": int(datetime.now().timestamp())
        }
        if requestid:
            data["requestid"] = requestid
        
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
    
    def _is_goal_active(self, goal_data: Dict[str, Any]) -> bool:
        """Check if goal is active (not finished/archived)"""
        # Goals with rate=0 and achieved target are typically finished
        rate = float(goal_data.get("rate") or 0)
        current = float(goal_data.get("curval", 0))
        target = float(goal_data.get("goalval") or 0)
        
        # Check for explicitly finished goals
        if rate == 0 and current >= target and target > 0:
            return False
            
        # Check for archived/paused goals (common indicators)
        goal_date = goal_data.get("goaldate")
        if goal_date:
            # Handle both timestamp (int) and string formats
            if isinstance(goal_date, int):
                goal_datetime = datetime.fromtimestamp(goal_date)
                if goal_datetime < datetime.now():
                    return False
            elif isinstance(goal_date, str):
                if goal_date < datetime.now().strftime("%Y-%m-%d"):
                    return False
            
        return True
    
    def _parse_goal(self, goal_data: Dict[str, Any]) -> BeeminderGoal:
        """Parse raw API response into structured BeeminderGoal"""
        # Ensure safebuf is an integer
        try:
            safebuf = int(goal_data.get("safebuf", 0))
        except (ValueError, TypeError):
            safebuf = 0
        
        return BeeminderGoal(
            slug=goal_data.get("slug", ""),
            title=goal_data.get("title", goal_data.get("slug", "")),
            current_value=float(goal_data.get("curval", 0)),
            target_value=float(goal_data.get("goalval") or 0),
            safebuf=safebuf,
            deadline=self._calculate_deadline(safebuf),
            derail_risk=self._classify_derail_risk(safebuf),
            pledge=float(goal_data.get("pledge", 0)),
            rate=float(goal_data.get("rate") or 0),
            runits=goal_data.get("runits", "d")
        )
    
    async def get_all_goals(self) -> List[Dict[str, Any]]:
        """Get all active goals with structured data and risk assessment"""
        raw_goals = await self.get_user_goals()
        
        structured_goals = []
        for goal_data in raw_goals:
            try:
                # Skip inactive/finished goals
                if not self._is_goal_active(goal_data):
                    logger.info(f"Skipping inactive goal: {goal_data.get('slug', 'unknown')}")
                    continue
                    
                goal = self._parse_goal(goal_data)
                structured_goals.append(goal.to_dict())
            except Exception as e:
                logger.error(f"Failed to parse goal {goal_data.get('slug', 'unknown')}: {e}")
                continue
        
        return structured_goals
    
    async def get_emergencies(self, all_goals: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Get goals requiring immediate attention (beemergencies)"""
        if all_goals is None:
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
                        message = f"{slug}: DERAILING NOW! Need data immediately"
                        time_remaining = "0 hours"
                    else:
                        message = f"{slug}: Derails in {safebuf} day(s)"
                        time_remaining = f"{safebuf * 24} hours"
                        
                elif risk == "WARNING":
                    urgency = "TODAY"
                    message = f"{slug}: Derails tomorrow - act today"
                    time_remaining = "24 hours"
                    
                else:  # CAUTION
                    urgency = "SOON"
                    message = f"{slug}: Derails in {safebuf} days"
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
    
    async def get_critical_goals(self, all_goals: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Get only goals in CRITICAL state (derailing today/already derailed)"""
        emergencies = await self.get_emergencies(all_goals)
        return [e for e in emergencies if e["urgency"] == "IMMEDIATE"]
    
    async def format_emergency_summary(self, all_goals: Optional[List[Dict[str, Any]]] = None) -> str:
        """Format emergency summary for narrator context"""
        emergencies = await self.get_emergencies(all_goals)
        
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
    
    async def get_runway_summary(self, limit: int = 4, all_goals: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Get most urgent goals plus bike goal for strategic visibility"""
        if all_goals is None:
            all_goals = await self.get_all_goals()
        
        # Sort ALL goals by urgency (shortest safebuf first, regardless of risk level)
        sorted_goals = sorted(all_goals, key=lambda x: x.get("safebuf", 999))
        
        # Always include bike goal if it exists, regardless of its urgency
        bike_goal = None
        for goal in all_goals:
            if "bike" in goal.get("slug", "").lower() or "bike" in goal.get("title", "").lower():
                bike_goal = goal
                break
        
        # Monitor ob_mirror goal for issues - alert if safebuf != 8 after 10am
        ob_mirror_alert = None
        current_hour = datetime.now().hour
        if current_hour >= 10:  # After 10am local time
            for goal in all_goals:
                if "ob_mirror" in goal.get("slug", "").lower() or "ob-mirror" in goal.get("slug", "").lower():
                    safebuf = goal.get("safebuf", 0)
                    if safebuf != 8:
                        ob_mirror_alert = {
                            "type": "OB_MIRROR_ANOMALY",
                            "message": f"🚨 OB Mirror safebuf is {safebuf}, expected 8 - server may need attention",
                            "goal_slug": goal.get("slug", ""),
                            "current_safebuf": safebuf,
                            "expected_safebuf": 8,
                            "time_detected": datetime.now().isoformat()
                        }
                    break
        
        # Take top N most urgent goals
        selected_goals = sorted_goals[:limit]
        
        # If bike goal exists and isn't already in the top N, replace the least urgent one
        if bike_goal and bike_goal not in selected_goals:
            if len(selected_goals) == limit:
                selected_goals[-1] = bike_goal  # Replace least urgent
            else:
                selected_goals.append(bike_goal)
        
        runway_info = []
        for goal in selected_goals:
            runway_info.append({
                "slug": goal.get("slug", ""),
                "title": goal.get("title", ""),
                "safebuf": goal.get("safebuf", 0),
                "runway": f"{goal.get('safebuf', 0)} days",
                "rate": goal.get("rate", 0),
                "runits": goal.get("runits", "d"),
                "derail_risk": goal.get("derail_risk", "SAFE")
            })
        
        # Add ob_mirror alert to runway info if detected
        if ob_mirror_alert:
            runway_info.append({
                "slug": "ALERT",
                "title": ob_mirror_alert["message"],
                "safebuf": 0,
                "runway": "IMMEDIATE",
                "rate": 0,
                "runits": "alert",
                "derail_risk": "OB_MIRROR_ANOMALY"
            })
        
        return runway_info
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()