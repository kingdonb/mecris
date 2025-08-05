"""
Mecris MCP Server - Personal LLM Accountability System
Main FastAPI application that aggregates multiple MCP sources
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv

from obsidian_client import ObsidianMCPClient
from beeminder_client import BeeminderClient
from usage_tracker import UsageTracker, get_budget_status, record_usage, update_remaining_budget, get_goals, complete_goal, add_goal
from twilio_sender import send_sms

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO if os.getenv("DEBUG") == "true" else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mecris")

app = FastAPI(
    title="Mecris MCP Server",
    description="Personal LLM Accountability System - Machine Context Provider",
    version="0.1.0"
)

# Initialize clients
obsidian_client = ObsidianMCPClient()
beeminder_client = BeeminderClient()
usage_tracker = UsageTracker()

# Daily activity cache - avoids hitting Beeminder API more than once per hour
daily_activity_cache = {
    # "bike": {
    #     "last_check": datetime.now(),
    #     "has_activity_today": False,
    #     "cache_expires": datetime.now() + timedelta(hours=1)
    # }
}

# PHASE 2: Beeminder goals cache - 30 minute TTL for goal data
beeminder_goals_cache = {
    # "data": [...],
    # "last_check": datetime.now(),
    # "cache_expires": datetime.now() + timedelta(minutes=30),
    # "is_stale": False
}

# Response models
class GoalResponse(BaseModel):
    goals: List[Dict[str, Any]]
    last_updated: datetime
    source: str

class TodoResponse(BaseModel):
    todos: List[Dict[str, Any]]
    completed_count: int
    pending_count: int
    source: str

class DailyNoteResponse(BaseModel):
    date: str
    content: str
    word_count: int
    source: str

class BeeminderStatusResponse(BaseModel):
    goals: List[Dict[str, Any]]
    emergencies: List[Dict[str, Any]]
    safe_count: int
    warning_count: int
    critical_count: int

class NarratorContextResponse(BaseModel):
    summary: str
    goals_status: Dict[str, Any]
    urgent_items: List[str]
    beeminder_alerts: List[str]
    goal_runway: List[Dict[str, Any]]
    budget_status: Dict[str, Any]
    recommendations: List[str]
    daily_walk_status: Optional[Dict[str, Any]] = None
    last_updated: datetime

class BudgetResponse(BaseModel):
    total_budget: float
    remaining_budget: float
    used_budget: float
    days_remaining: int
    today_spend: float
    daily_burn_rate: float
    projected_spend: float
    period_end: str
    alerts: List[str]
    budget_health: str

# Cache helper functions
async def get_cached_beeminder_goals() -> List[Dict[str, Any]]:
    """Get Beeminder goals with 30-minute cache to improve narrator context performance"""
    now = datetime.now()
    
    # Check if we have valid cached data
    if ("data" in beeminder_goals_cache and 
        "cache_expires" in beeminder_goals_cache and 
        now < beeminder_goals_cache["cache_expires"]):
        logger.info("Using cached Beeminder goals")
        beeminder_goals_cache["is_stale"] = False
        return beeminder_goals_cache["data"]
    
    # Cache expired or doesn't exist - fetch from Beeminder API
    try:
        logger.info("Fetching fresh Beeminder goals from API")
        goals_data = await beeminder_client.get_all_goals()
        
        # Update cache with 30-minute expiration
        beeminder_goals_cache.update({
            "data": goals_data,
            "last_check": now,
            "cache_expires": now + timedelta(minutes=30),
            "is_stale": False
        })
        
        return goals_data
        
    except Exception as e:
        logger.error(f"Failed to fetch Beeminder goals: {e}")
        # Return cached data if available, even if expired (mark as stale)
        if "data" in beeminder_goals_cache and beeminder_goals_cache["data"]:
            logger.warning("Using stale Beeminder goals cache due to API error")
            beeminder_goals_cache["is_stale"] = True
            return beeminder_goals_cache["data"]
        else:
            # No cache and API failed - return empty list
            logger.error("No cached goals available and API failed")
            return []

async def get_cached_daily_activity(goal_slug: str = "bike") -> Dict[str, Any]:
    """Get daily activity status with 1-hour cache to respect API limits"""
    now = datetime.now()
    
    # Check if we have valid cached data
    if goal_slug in daily_activity_cache:
        cache_entry = daily_activity_cache[goal_slug]
        if now < cache_entry["cache_expires"]:
            logger.info(f"Using cached activity status for {goal_slug}")
            return {
                "goal_slug": goal_slug,
                "has_activity_today": cache_entry["has_activity_today"],
                "status": "completed" if cache_entry["has_activity_today"] else "needed",
                "cached": True,
                "last_check": cache_entry["last_check"].isoformat(),
                "message": f"✅ Walk logged today" if cache_entry["has_activity_today"] else "🚶‍♂️ No walk detected today"
            }
    
    # Cache expired or doesn't exist - fetch from Beeminder API
    try:
        logger.info(f"Fetching fresh activity status for {goal_slug} from Beeminder")
        activity_status = await beeminder_client.get_daily_activity_status(goal_slug)
        
        # Update cache with 1-hour expiration
        daily_activity_cache[goal_slug] = {
            "last_check": now,
            "has_activity_today": activity_status["has_activity_today"],
            "cache_expires": now + timedelta(hours=1)
        }
        
        # Add cache info to response
        activity_status["cached"] = False
        return activity_status
        
    except Exception as e:
        logger.error(f"Failed to fetch daily activity for {goal_slug}: {e}")
        # Return cached data if available, even if expired
        if goal_slug in daily_activity_cache:
            cache_entry = daily_activity_cache[goal_slug]
            return {
                "goal_slug": goal_slug,
                "has_activity_today": cache_entry["has_activity_today"],
                "status": "completed" if cache_entry["has_activity_today"] else "needed",
                "cached": True,
                "last_check": cache_entry["last_check"].isoformat(),
                "message": f"⚠️ Using stale cache (API error)",
                "error": str(e)
            }
        else:
            # No cache and API failed
            return {
                "goal_slug": goal_slug,
                "has_activity_today": False,
                "status": "unknown",
                "cached": False,
                "message": "❌ Unable to check activity status",
                "error": str(e)
            }

# Health check
@app.get("/")
async def root():
    return {
        "service": "Mecris MCP Server",
        "status": "operational",
        "version": "0.1.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Enhanced health check endpoint with service status"""
    import time
    start_time = time.time()
    
    status = {
        "mecris": "ok",
        "obsidian": "unknown",
        "beeminder": "unknown", 
        "usage_tracker": "ok",
        "twilio": "not_configured"
    }
    
    # Test Obsidian client
    try:
        status["obsidian"] = await obsidian_client.health_check()
    except Exception as e:
        status["obsidian"] = f"error: {str(e)[:50]}"
    
    # Test Beeminder client  
    try:
        status["beeminder"] = await beeminder_client.health_check()
    except Exception as e:
        status["beeminder"] = f"error: {str(e)[:50]}"
    
    # Test Twilio configuration
    if os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"):
        status["twilio"] = "configured"
    
    # Test usage tracker
    try:
        budget_status = get_budget_status()
        if "error" not in budget_status:
            status["usage_tracker"] = "ok"
        else:
            status["usage_tracker"] = "error"
    except Exception:
        status["usage_tracker"] = "error"
    
    # Determine overall health
    critical_services = ["mecris", "usage_tracker"]
    critical_healthy = all(status[s] == "ok" for s in critical_services)
    
    response_time = round((time.time() - start_time) * 1000, 2)  # ms
    
    if critical_healthy:
        overall_status = "healthy"
    else:
        overall_status = "unhealthy"
    
    return {
        "status": overall_status,
        "services": status,
        "response_time_ms": response_time,
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0"
    }

# Goals endpoints (local database)
@app.get("/goals", response_model=GoalResponse)
async def get_goals_endpoint():
    """Get goals from local database"""
    try:
        goals_data = get_goals()
        return GoalResponse(
            goals=goals_data,
            last_updated=datetime.now(),
            source="database"
        )
    except Exception as e:
        logger.error(f"Failed to fetch goals: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch goals from database")

@app.post("/goals/{goal_id}/complete")
async def complete_goal_endpoint(goal_id: int):
    """Mark a goal as completed"""
    try:
        result = complete_goal(goal_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as e:
        logger.error(f"Failed to complete goal {goal_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete goal")

@app.post("/goals")
async def add_goal_endpoint(title: str, description: str = "", priority: str = "medium", due_date: Optional[str] = None):
    """Add a new goal"""
    try:
        result = add_goal(title, description, priority, due_date)
        return result
    except Exception as e:
        logger.error(f"Failed to add goal: {e}")
        raise HTTPException(status_code=500, detail="Failed to add goal")

@app.get("/todos", response_model=TodoResponse)
async def get_todos():
    """Extract todos from Obsidian vault"""
    try:
        todos_data = await obsidian_client.get_todos()
        completed = len([t for t in todos_data if t.get("completed", False)])
        pending = len(todos_data) - completed
        
        return TodoResponse(
            todos=todos_data,
            completed_count=completed,
            pending_count=pending,
            source="obsidian"
        )
    except Exception as e:
        logger.error(f"Failed to fetch todos: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch todos from Obsidian")

@app.get("/daily/{date}", response_model=DailyNoteResponse)
async def get_daily_note(date: str):
    """Get daily note content for specific date (YYYY-MM-DD format)"""
    try:
        # Validate date format
        datetime.strptime(date, "%Y-%m-%d")
        
        content = await obsidian_client.get_daily_note(date)
        word_count = len(content.split()) if content else 0
        
        return DailyNoteResponse(
            date=date,
            content=content,
            word_count=word_count,
            source="obsidian"
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Failed to fetch daily note for {date}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch daily note for {date}")

# Beeminder endpoints
@app.get("/beeminder/status", response_model=BeeminderStatusResponse)
async def get_beeminder_status():
    """Get overall Beeminder goal portfolio status"""
    try:
        goals = await beeminder_client.get_all_goals()
        emergencies = await beeminder_client.get_emergencies()
        
        # Count by risk level
        safe = len([g for g in goals if g.get("derail_risk") == "SAFE"])
        warning = len([g for g in goals if g.get("derail_risk") in ["WARNING", "CAUTION"]])
        critical = len([g for g in goals if g.get("derail_risk") == "CRITICAL"])
        
        return BeeminderStatusResponse(
            goals=goals,
            emergencies=emergencies,
            safe_count=safe,
            warning_count=warning,
            critical_count=critical
        )
    except Exception as e:
        logger.error(f"Failed to fetch Beeminder status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch Beeminder status")

@app.get("/beeminder/emergency")
async def get_beeminder_emergencies():
    """Get goals requiring immediate attention"""
    try:
        emergencies = await beeminder_client.get_emergencies()
        return {
            "emergencies": emergencies,
            "count": len(emergencies),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to fetch beemergencies: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch emergency goals")

@app.post("/beeminder/alert")
async def send_beeminder_alert(background_tasks: BackgroundTasks):
    """Check for beemergencies and send SMS alerts if needed"""
    try:
        emergencies = await beeminder_client.get_emergencies()
        critical_emergencies = [e for e in emergencies if e.get("urgency") == "IMMEDIATE"]
        
        tracker = UsageTracker()
        
        if critical_emergencies:
            # Use shorter cooldown for beemergencies since they're time-critical
            if tracker.should_send_alert("beeminder", "critical", cooldown_minutes=90):
                alert_message = f"🚨 BEEMERGENCY: {len(critical_emergencies)} goals need immediate attention!"
                for emergency in critical_emergencies[:3]:  # Limit to 3 in SMS
                    alert_message += f"\n• {emergency['goal_slug']}: {emergency['message']}"
                
                # Send SMS in background
                background_tasks.add_task(send_sms, alert_message)
                tracker.log_alert("beeminder", "critical", alert_message, f"critical_count: {len(critical_emergencies)}")
                
                return {
                    "alert_sent": True,
                    "critical_count": len(critical_emergencies),
                    "message": "Beemergency alert sent"
                }
            else:
                return {
                    "alert_sent": False,
                    "critical_count": len(critical_emergencies),
                    "message": "Beemergency alert on cooldown",
                    "reason": "cooldown_active"
                }
        
        return {
            "alert_sent": False,
            "critical_count": 0,
            "message": "No critical emergencies found"
        }
        
    except Exception as e:
        logger.error(f"Failed to send beeminder alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to process beeminder alert")

@app.get("/beeminder/daily-activity/{goal_slug}")
async def get_daily_activity(goal_slug: str = "bike"):
    """Check if daily activity was logged for specified goal (with 1-hour cache)"""
    try:
        activity_status = await get_cached_daily_activity(goal_slug)
        return {
            "activity_status": activity_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to check daily activity for {goal_slug}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check daily activity for {goal_slug}")

@app.get("/beeminder/daily-activity")
async def get_daily_activity_default():
    """Check if daily activity was logged for bike goal (default)"""
    return await get_daily_activity("bike")

# Usage tracking endpoints
@app.get("/usage", response_model=BudgetResponse)
async def get_usage_status():
    """Get current usage and budget status"""
    try:
        budget_data = get_budget_status()
        
        if "error" in budget_data:
            raise HTTPException(status_code=500, detail=budget_data["error"])
        
        return BudgetResponse(**budget_data)
        
    except Exception as e:
        logger.error(f"Failed to fetch usage status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch usage status")

@app.post("/usage/record")
async def record_usage_session(input_tokens: int, output_tokens: int, model: str = "claude-3-5-sonnet-20241022", session_type: str = "interactive", notes: str = ""):
    """Record a usage session with token counts"""
    try:
        cost = record_usage(input_tokens, output_tokens, model, session_type, notes)
        
        updated_status = get_budget_status()
        return {
            "recorded": True,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost": cost,
            "model": model,
            "session_type": session_type,
            "updated_status": updated_status,
            "timestamp": datetime.now().isoformat()
        }
            
    except Exception as e:
        logger.error(f"Failed to record usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to record usage")

@app.post("/usage/update_budget")
async def update_budget(remaining_budget: float, total_budget: Optional[float] = None, period_end: Optional[str] = None):
    """Manually update budget information"""
    try:
        if total_budget or period_end:
            # Use full budget update from usage tracker
            tracker = UsageTracker()
            updated_budget = tracker.update_budget(remaining_budget, total_budget, period_end)
        else:
            # Use existing convenience function for remaining budget only  
            updated_budget = update_remaining_budget(remaining_budget)
        
        return {
            "updated": True,
            "budget_info": updated_budget,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to update budget: {e}")
        raise HTTPException(status_code=500, detail="Failed to update budget")

@app.get("/usage/summary")
async def get_usage_summary(days: int = 7):
    """Get detailed usage summary for the last N days"""
    try:
        summary = usage_tracker.get_usage_summary(days)
        return {
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get usage summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get usage summary")

@app.get("/usage/recent")
async def get_recent_sessions(limit: int = 10):
    """Get recent usage sessions"""
    try:
        sessions = usage_tracker.get_recent_sessions(limit)
        return {
            "sessions": sessions,
            "count": len(sessions),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get recent sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recent sessions")

@app.post("/usage/alert")
async def send_usage_alert(background_tasks: BackgroundTasks):
    """Check usage status and send alerts if needed"""
    try:
        budget_data = get_budget_status()
        
        if "error" in budget_data:
            return {"alert_sent": False, "error": budget_data["error"]}
        
        days_remaining = budget_data.get("days_remaining", float('inf'))
        remaining_budget = budget_data.get("remaining_budget", 0)
        alerts = budget_data.get("alerts", [])
        
        # Check spam protection
        tracker = UsageTracker()
        
        if "CRITICAL" in budget_data.get("budget_health", "") or days_remaining <= 1:
            if tracker.should_send_alert("budget", "critical", cooldown_minutes=120):  # 2 hour cooldown for critical
                alert_msg = f"🚨 CRITICAL: {days_remaining} days left!\n${remaining_budget:.2f} remaining"
                background_tasks.add_task(send_sms, alert_msg)
                tracker.log_alert("budget", "critical", alert_msg, f"days_remaining: {days_remaining}, budget: {remaining_budget}")
                return {"alert_sent": True, "level": "critical", "days_remaining": days_remaining}
            else:
                return {"alert_sent": False, "level": "critical", "reason": "cooldown_active", "days_remaining": days_remaining}
        elif "WARNING" in budget_data.get("budget_health", "") or days_remaining <= 2:
            if tracker.should_send_alert("budget", "warning", cooldown_minutes=360):  # 6 hour cooldown for warnings
                alert_msg = f"⚠️ WARNING: {days_remaining} days left\n${remaining_budget:.2f} remaining"
                background_tasks.add_task(send_sms, alert_msg)
                tracker.log_alert("budget", "warning", alert_msg, f"days_remaining: {days_remaining}, budget: {remaining_budget}")
                return {"alert_sent": True, "level": "warning", "days_remaining": days_remaining}
            else:
                return {"alert_sent": False, "level": "warning", "reason": "cooldown_active", "days_remaining": days_remaining}
        
        return {"alert_sent": False, "level": "safe", "days_remaining": days_remaining}
        
    except Exception as e:
        logger.error(f"Failed to send usage alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to process usage alert")

# PHASE 2: Cache management endpoints
@app.get("/cache/status")
async def get_cache_status():
    """Get cache status for monitoring"""
    now = datetime.now()
    
    # Daily activity cache status
    daily_cache_status = {}
    for goal_slug, cache_data in daily_activity_cache.items():
        daily_cache_status[goal_slug] = {
            "cached": True,
            "expires": cache_data["cache_expires"].isoformat(),
            "valid": now < cache_data["cache_expires"],
            "age_minutes": (now - cache_data["last_check"]).total_seconds() / 60
        }
    
    # Beeminder goals cache status
    goals_cache_status = {}
    if "data" in beeminder_goals_cache:
        goals_cache_status = {
            "cached": True,
            "count": len(beeminder_goals_cache["data"]),
            "expires": beeminder_goals_cache["cache_expires"].isoformat(),
            "valid": now < beeminder_goals_cache["cache_expires"],
            "is_stale": beeminder_goals_cache.get("is_stale", False),
            "age_minutes": (now - beeminder_goals_cache["last_check"]).total_seconds() / 60
        }
    else:
        goals_cache_status = {"cached": False}
    
    return {
        "cache_status": {
            "daily_activity": daily_cache_status,
            "beeminder_goals": goals_cache_status
        },
        "timestamp": now.isoformat()
    }

@app.post("/cache/clear")
async def clear_cache(cache_type: str = "all"):
    """Clear specific cache or all caches"""
    cleared = []
    
    if cache_type in ["all", "daily_activity"]:
        daily_activity_cache.clear()
        cleared.append("daily_activity")
    
    if cache_type in ["all", "beeminder_goals"]:
        beeminder_goals_cache.clear()
        cleared.append("beeminder_goals")
    
    return {
        "cleared": cleared,
        "message": f"Cache cleared: {', '.join(cleared)}",
        "timestamp": datetime.now().isoformat()
    }

# Unified narrator context
@app.get("/narrator/context", response_model=NarratorContextResponse)
async def get_narrator_context():
    """Unified context for Claude narrator with strategic insights"""
    try:
        # Gather data from all sources
        goals = get_goals()  # Use local goals instead of Obsidian
        active_goals = [g for g in goals if g.get("status") == "active"] 
        try:
            todos = await obsidian_client.get_todos()  # Keep trying Obsidian for todos
        except:
            todos = []  # Fallback if Obsidian not available
        # PHASE 2 OPTIMIZATION: Cached Beeminder goals + derived views
        beeminder_goals = await get_cached_beeminder_goals()
        emergencies = await beeminder_client.get_emergencies(beeminder_goals)
        goal_runway = await beeminder_client.get_runway_summary(limit=6, all_goals=beeminder_goals)
        
        budget_status = get_budget_status()
        
        # Get daily walk status (cached for performance)
        daily_walk_status = await get_cached_daily_activity("bike")
        
        # Build strategic summary
        pending_todos = [t for t in todos if not t.get("completed", False)]
        critical_beeminder = [g for g in beeminder_goals if g.get("derail_risk") == "CRITICAL"]
        
        # Enhanced summary with budget info
        budget_days = budget_status.get("days_remaining", 0)
        summary = f"Active goals: {len(active_goals)}, Pending todos: {len(pending_todos)}, Beeminder goals: {len(beeminder_goals)}, Budget: {budget_days:.1f} days left"
        
        urgent_items = []
        if critical_beeminder:
            urgent_items.extend([f"DERAILING: {g['slug']}" for g in critical_beeminder])
        
        # Add budget urgency
        if budget_days <= 1:
            urgent_items.append(f"BUDGET CRITICAL: {budget_days:.1f} days left")
        elif budget_days <= 2:
            urgent_items.append(f"BUDGET WARNING: {budget_days:.1f} days left")
        
        beeminder_alerts = [e.get("message", "") for e in emergencies[:5]]
        
        recommendations = []
        if len(pending_todos) > 10:
            recommendations.append("Consider prioritizing todos - large backlog detected")
        if critical_beeminder:
            recommendations.append("Address critical Beeminder goals immediately")
        if budget_days <= 2:
            recommendations.append("Urgent: Focus on highest-value work due to budget constraints")
        if not active_goals:
            recommendations.append("No active goals found - consider setting objectives")
        
        # Add walk reminder if needed and it's afternoon
        current_hour = datetime.now().hour
        if (daily_walk_status.get("status") == "needed" and 
            current_hour >= 14):  # After 2 PM
            recommendations.append("🚶‍♂️ Time for a walk! No activity logged today for bike goal")
        
        return NarratorContextResponse(
            summary=summary,
            goals_status={"total": len(active_goals), "sources": ["database"]},
            urgent_items=urgent_items,
            beeminder_alerts=beeminder_alerts,
            goal_runway=goal_runway,
            budget_status=budget_status,
            recommendations=recommendations,
            daily_walk_status=daily_walk_status,
            last_updated=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to build narrator context: {e}")
        raise HTTPException(status_code=500, detail="Failed to build narrator context")

# Session logging
@app.post("/log-session")
async def log_session(session_data: Dict[str, Any]):
    """Log session summary back to Obsidian"""
    try:
        timestamp = datetime.now().isoformat()
        log_entry = f"\n## Session Log - {timestamp}\n"
        log_entry += f"Duration: {session_data.get('duration', 'unknown')}\n"
        log_entry += f"Actions: {session_data.get('actions_taken', [])}\n"
        log_entry += f"Outcomes: {session_data.get('outcomes', 'none specified')}\n"
        
        await obsidian_client.append_to_session_log(log_entry)
        
        return {
            "logged": True,
            "timestamp": timestamp,
            "message": "Session logged to Obsidian"
        }
        
    except Exception as e:
        logger.error(f"Failed to log session: {e}")
        raise HTTPException(status_code=500, detail="Failed to log session")

# Intelligent Reminder System
@app.get("/intelligent-reminder/check")
async def check_reminder_needed():
    """Check if any reminders should be sent - works without Claude credits"""
    try:
        # Get full MCP context without consuming Claude credits
        context_response = await get_narrator_context()
        context = context_response if isinstance(context_response, dict) else {}
        
        current_time = datetime.now()
        current_hour = current_time.hour
        
        # Budget tier assessment from context
        budget_status = context.get("budget_status", {})
        remaining_budget = budget_status.get("remaining_budget", 0)
        
        # Determine messaging tier based on budget
        if remaining_budget > 2.0:
            tier = "enhanced"  # Claude available for sophisticated analysis
        elif remaining_budget > 0.5:
            tier = "smart_template"  # Claude constrained, use templates with full context
        else:
            tier = "base_mode"  # Claude exhausted, basic reminders only
        
        # Walk status from MCP context
        daily_walk_status = context.get("daily_walk_status", {})
        walk_needed = daily_walk_status.get("status") == "needed"
        
        # Base mode: Only walk reminders, 2-5 PM window
        if tier == "base_mode":
            if walk_needed and 14 <= current_hour <= 17:
                import random
                messages = [
                    "🚶‍♂️ Walk reminder - dogs are waiting!",
                    "🐕 Time for that daily walk",
                    "🚶‍♂️ No walk logged yet today - time to move!"
                ]
                return {
                    "should_send": True,
                    "tier": tier,
                    "message": random.choice(messages),
                    "type": "walk_reminder",
                    "budget_remaining": remaining_budget
                }
            return {"should_send": False, "tier": tier, "reason": "No walk needed or outside time window"}
        
        # Smart template mode: Full context analysis with templates
        elif tier == "smart_template":
            # Primary: Walk reminders (afternoon window)
            if walk_needed and 14 <= current_hour <= 17:
                # Get bike goal info for context
                goal_runway = context.get("goal_runway", [])
                bike_goal = next((g for g in goal_runway if "bike" in g.get("slug", "").lower()), None)
                
                if bike_goal:
                    safebuf = bike_goal.get("safebuf", 0)
                    message = f"🚶‍♂️ No walk logged yet today - your bike goal needs progress ({safebuf} days safe) and the dogs need exercise!"
                else:
                    message = "🚶‍♂️ Walk reminder - no activity logged today and the dogs are waiting!"
                
                return {
                    "should_send": True,
                    "tier": tier,
                    "message": message,
                    "type": "walk_reminder",
                    "budget_remaining": remaining_budget
                }
            
            # Secondary: Check for other urgent items (budget warnings, etc.)
            urgent_items = context.get("urgent_items", [])
            if urgent_items and 9 <= current_hour <= 17:
                budget_critical = any("BUDGET CRITICAL" in item for item in urgent_items)
                if budget_critical:
                    return {
                        "should_send": True,
                        "tier": tier,
                        "message": f"💰 Budget alert: ${remaining_budget:.2f} remaining. Focus mode activated.",
                        "type": "budget_warning",
                        "budget_remaining": remaining_budget
                    }
            
            return {"should_send": False, "tier": tier, "reason": "No urgent items in appropriate time window"}
        
        # Enhanced mode: Would use Claude for sophisticated analysis
        # For now, fall back to smart template behavior
        else:  # tier == "enhanced"
            # TODO: Implement Claude-enhanced decision making
            # For now, use smart template logic
            if walk_needed and 14 <= current_hour <= 17:
                return {
                    "should_send": True,
                    "tier": "smart_template",  # Fallback for now
                    "message": "🚶‍♂️ Perfect timing for a walk! No activity logged today and the dogs need their exercise.",
                    "type": "walk_reminder",
                    "budget_remaining": remaining_budget,
                    "note": "Enhanced mode not yet implemented, using smart template"
                }
            
            return {"should_send": False, "tier": tier, "reason": "No walk needed or outside time window"}
            
    except Exception as e:
        logger.error(f"Failed to check reminder status: {e}")
        # Graceful degradation - return a basic walk reminder if it's afternoon
        current_hour = datetime.now().hour
        if 14 <= current_hour <= 17:
            return {
                "should_send": True,
                "tier": "emergency_fallback",
                "message": "🚶‍♂️ Walk reminder - system degraded but dogs still need walking!",
                "type": "walk_reminder",
                "error": str(e)
            }
        
        return {"should_send": False, "error": str(e)}

@app.post("/intelligent-reminder/send")
async def send_reminder_message(message_data: Dict[str, Any]):
    """Send reminder message via WhatsApp/SMS with no-spam protection"""
    try:
        # Import Twilio sender
        from twilio_sender import send_message, send_sms
        
        message = message_data.get("message", "")
        message_type = message_data.get("type", "walk_reminder")
        tier = message_data.get("tier", "base_mode")
        
        if not message:
            return {"sent": False, "error": "No message provided"}
        
        # No-spam protection: Check if we've already sent this type today
        from datetime import date
        import json
        
        # Simple file-based tracking for no-spam
        spam_file = "/tmp/mecris_daily_messages.json"
        today = str(date.today())
        
        # Load existing message log
        daily_messages = {}
        try:
            if os.path.exists(spam_file):
                with open(spam_file, 'r') as f:
                    daily_messages = json.load(f)
        except:
            daily_messages = {}
        
        # Check if we've already sent this type today
        if today in daily_messages:
            if message_type in daily_messages[today]:
                return {
                    "sent": False, 
                    "reason": "Already sent this message type today",
                    "message_type": message_type,
                    "last_sent": daily_messages[today][message_type]
                }
        
        # Try WhatsApp first, fall back to SMS
        success = False
        delivery_method = None
        
        # Attempt WhatsApp delivery
        if send_message(message):
            success = True
            delivery_method = "whatsapp"
            logger.info(f"WhatsApp message sent: {message}")
        elif send_sms(message):
            success = True
            delivery_method = "sms"
            logger.info(f"SMS fallback sent: {message}")
        
        if success:
            # Log successful send to prevent spam
            if today not in daily_messages:
                daily_messages[today] = {}
            daily_messages[today][message_type] = {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "tier": tier,
                "delivery_method": delivery_method
            }
            
            # Save updated log
            try:
                with open(spam_file, 'w') as f:
                    json.dump(daily_messages, f)
            except Exception as e:
                logger.warning(f"Failed to update no-spam log: {e}")
            
            return {
                "sent": True,
                "delivery_method": delivery_method,
                "message_type": message_type,
                "tier": tier,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "sent": False,
                "error": "Both WhatsApp and SMS delivery failed",
                "message_type": message_type
            }
            
    except Exception as e:
        logger.error(f"Failed to send reminder message: {e}")
        return {"sent": False, "error": str(e)}

@app.post("/intelligent-reminder/trigger")
async def trigger_reminder_check():
    """Check for needed reminders and send them - complete workflow"""
    try:
        # Check if reminder is needed
        check_result = await check_reminder_needed()
        
        if not check_result.get("should_send", False):
            return {
                "triggered": False,
                "reason": check_result.get("reason", "No reminder needed"),
                "tier": check_result.get("tier", "unknown")
            }
        
        # Send the message
        send_result = await send_reminder_message({
            "message": check_result.get("message", ""),
            "type": check_result.get("type", "walk_reminder"),
            "tier": check_result.get("tier", "base_mode")
        })
        
        return {
            "triggered": True,
            "check_result": check_result,
            "send_result": send_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger reminder: {e}")
        return {"triggered": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "mcp_server:app",
        host="127.0.0.1",  # Secure localhost binding
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )