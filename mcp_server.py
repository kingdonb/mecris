"""
Mecris MCP Server - Personal LLM Accountability System
Main FastAPI application that aggregates multiple MCP sources
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv

from obsidian_client import ObsidianMCPClient
from beeminder_client import BeeminderClient
from usage_tracker import UsageTracker, get_budget_status, record_usage, update_remaining_budget
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

# Obsidian endpoints
@app.get("/goals", response_model=GoalResponse)
async def get_goals():
    """Extract goals from Obsidian vault"""
    try:
        goals_data = await obsidian_client.get_goals()
        return GoalResponse(
            goals=goals_data,
            last_updated=datetime.now(),
            source="obsidian"
        )
    except Exception as e:
        logger.error(f"Failed to fetch goals: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch goals from Obsidian")

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
        
        if critical_emergencies:
            alert_message = f"🚨 BEEMERGENCY: {len(critical_emergencies)} goals need immediate attention!"
            for emergency in critical_emergencies[:3]:  # Limit to 3 in SMS
                alert_message += f"\n• {emergency['goal_slug']}: {emergency['message']}"
            
            # Send SMS in background
            background_tasks.add_task(send_sms, alert_message)
            
            return {
                "alert_sent": True,
                "critical_count": len(critical_emergencies),
                "message": "Beemergency alert sent"
            }
        
        return {
            "alert_sent": False,
            "critical_count": 0,
            "message": "No critical emergencies found"
        }
        
    except Exception as e:
        logger.error(f"Failed to send beeminder alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to process beeminder alert")

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
async def update_budget(remaining_budget: float):
    """Manually update remaining budget amount"""
    try:
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
        
        if "CRITICAL" in budget_data.get("budget_health", "") or days_remaining <= 1:
            alert_msg = f"🚨 CRITICAL: {days_remaining} days left!\n${remaining_budget:.2f} remaining"
            background_tasks.add_task(send_sms, alert_msg)
            return {"alert_sent": True, "level": "critical", "days_remaining": days_remaining}
        elif "WARNING" in budget_data.get("budget_health", "") or days_remaining <= 2:
            alert_msg = f"⚠️ WARNING: {days_remaining} days left\n${remaining_budget:.2f} remaining"
            background_tasks.add_task(send_sms, alert_msg)
            return {"alert_sent": True, "level": "warning", "days_remaining": days_remaining}
        
        return {"alert_sent": False, "level": "safe", "days_remaining": days_remaining}
        
    except Exception as e:
        logger.error(f"Failed to send usage alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to process usage alert")

# Unified narrator context
@app.get("/narrator/context", response_model=NarratorContextResponse)
async def get_narrator_context():
    """Unified context for Claude narrator with strategic insights"""
    try:
        # Gather data from all sources
        goals = await obsidian_client.get_goals()
        todos = await obsidian_client.get_todos()
        beeminder_status = await beeminder_client.get_all_goals()
        emergencies = await beeminder_client.get_emergencies()
        budget_status = get_budget_status()
        
        # Build strategic summary
        pending_todos = [t for t in todos if not t.get("completed", False)]
        critical_beeminder = [g for g in beeminder_status if g.get("derail_risk") == "CRITICAL"]
        
        # Enhanced summary with budget info
        budget_days = budget_status.get("days_remaining", 0)
        summary = f"Active goals: {len(goals)}, Pending todos: {len(pending_todos)}, Beeminder goals: {len(beeminder_status)}, Budget: {budget_days:.1f} days left"
        
        urgent_items = []
        if critical_beeminder:
            urgent_items.extend([f"DERAILING: {g['slug']}" for g in critical_beeminder])
        
        # Add budget urgency
        if budget_days <= 1:
            urgent_items.append(f"BUDGET CRITICAL: {budget_days:.1f} days left")
        elif budget_days <= 2:
            urgent_items.append(f"BUDGET WARNING: {budget_days:.1f} days left")
        
        beeminder_alerts = [e.get("message", "") for e in emergencies[:5]]
        
        # Always get runway info (most urgent goals + bike goal)
        goal_runway = await beeminder_client.get_runway_summary(limit=4)
        
        recommendations = []
        if len(pending_todos) > 10:
            recommendations.append("Consider prioritizing todos - large backlog detected")
        if critical_beeminder:
            recommendations.append("Address critical Beeminder goals immediately")
        if budget_days <= 2:
            recommendations.append("Urgent: Focus on highest-value work due to budget constraints")
        if not goals:
            recommendations.append("No active goals found - consider setting objectives")
        
        return NarratorContextResponse(
            summary=summary,
            goals_status={"total": len(goals), "sources": ["obsidian"]},
            urgent_items=urgent_items,
            beeminder_alerts=beeminder_alerts,
            goal_runway=goal_runway,
            budget_status=budget_status,
            recommendations=recommendations,
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "mcp_server:app",
        host="127.0.0.1",  # Secure localhost binding
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )