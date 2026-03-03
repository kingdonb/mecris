"""
Mecris MCP Server - Personal LLM Accountability System
This version is refactored to use the MCP Python SDK for stdio communication with the Handler Pattern.
"""

import os
import logging
import asyncio
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI

from obsidian_client import ObsidianMCPClient
from beeminder_client import BeeminderClient
from usage_tracker import UsageTracker, get_budget_status as get_budget_status_from_tracker, record_usage, update_remaining_budget, get_goals, complete_goal as complete_goal_from_tracker, add_goal as add_goal_from_tracker
from virtual_budget_manager import VirtualBudgetManager
from billing_reconciliation import BillingReconciliation
from groq_odometer_tracker import get_groq_context_for_narrator, get_groq_reminder_status, record_groq_reading as record_groq_reading_from_tracker
from twilio_sender import smart_send_message, send_sms
from scripts.anthropic_cost_tracker import AnthropicCostTracker
from services.weather_service import WeatherService

# Load environment variables
load_dotenv()

# Configure logging to stderr with ERROR level
logging.basicConfig(
    level=logging.ERROR,
    stream=sys.stderr,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mecris")

# Initialize the MCP Server
mcp = FastMCP("mecris")

# Create FastAPI app for HTTP endpoints
app = FastAPI(title="Mecris API")

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/intelligent-reminder/trigger")
async def trigger_reminder_endpoint():
    return await trigger_reminder_check()

@app.get("/narrator/context")
async def narrator_context_endpoint():
    return await get_narrator_context()

@app.get("/beeminder/status")
async def beeminder_status_endpoint():
    return await get_beeminder_status()

@app.get("/budget/status")
async def budget_status_endpoint():
    return get_budget_status()

# Mount the MCP server's ASGI app
# This allows the same process to serve both the MCP protocol (via stdio or SSE) 
# and custom HTTP endpoints.
app.mount("/mcp", mcp.sse_app())

# Initialize clients
obsidian_client = ObsidianMCPClient()
beeminder_client = BeeminderClient()
usage_tracker = UsageTracker()
virtual_budget_manager = VirtualBudgetManager()
billing_reconciler = BillingReconciliation()
weather_service = WeatherService()
try:
    anthropic_cost_tracker = AnthropicCostTracker()
except Exception as e:
    logger.warning(f"Failed to initialize AnthropicCostTracker: {e}")
    anthropic_cost_tracker = None

# --- Cache Implementation ---
daily_activity_cache = {}
beeminder_goals_cache = {}

async def get_cached_beeminder_goals() -> List[Dict[str, Any]]:
    """Get Beeminder goals with 30-minute cache."""
    now = datetime.now()
    if ("data" in beeminder_goals_cache and "cache_expires" in beeminder_goals_cache and now < beeminder_goals_cache["cache_expires"]):
        beeminder_goals_cache["is_stale"] = False
        return beeminder_goals_cache["data"]
    
    try:
        goals_data = await beeminder_client.get_all_goals()
        beeminder_goals_cache.update({
            "data": goals_data, "last_check": now, "cache_expires": now + timedelta(minutes=30), "is_stale": False
        })
        return goals_data
    except Exception as e:
        logger.error(f"Failed to fetch Beeminder goals: {e}")
        if "data" in beeminder_goals_cache:
            beeminder_goals_cache["is_stale"] = True
            return beeminder_goals_cache["data"]
        return []

async def get_cached_daily_activity(goal_slug: str = "bike") -> Dict[str, Any]:
    """Get daily activity status with 1-hour cache."""
    now = datetime.now()
    if goal_slug in daily_activity_cache:
        cache_entry = daily_activity_cache[goal_slug]
        if now < cache_entry["cache_expires"]:
            return {"goal_slug": goal_slug, "has_activity_today": cache_entry["has_activity_today"], "status": "completed" if cache_entry["has_activity_today"] else "needed", "cached": True}

    try:
        activity_status = await beeminder_client.get_daily_activity_status(goal_slug)
        daily_activity_cache[goal_slug] = {"last_check": now, "has_activity_today": activity_status["has_activity_today"], "cache_expires": now + timedelta(hours=1)}
        activity_status["cached"] = False
        return activity_status
    except Exception as e:
        logger.error(f"Failed to fetch daily activity for {goal_slug}: {e}")
        if goal_slug in daily_activity_cache:
            return {"goal_slug": goal_slug, "has_activity_today": daily_activity_cache[goal_slug]["has_activity_today"], "status": "stale", "error": str(e)}
        return {"goal_slug": goal_slug, "has_activity_today": False, "status": "unknown", "error": str(e)}

# --- Tool Implementations ---

@mcp.tool(description="Get unified strategic context with goals, budget, and recommendations.")
async def get_narrator_context() -> Dict[str, Any]:
    """Get unified strategic context with goals, budget, and recommendations."""
    try:
        goals = get_goals()
        active_goals = [g for g in goals if g.get("status") == "active"]
        try:
            todos = await obsidian_client.get_todos()
        except Exception:
            todos = []
        
        beeminder_goals = await get_cached_beeminder_goals()
        emergencies = await beeminder_client.get_emergencies(beeminder_goals)
        goal_runway = await beeminder_client.get_runway_summary(limit=6, all_goals=beeminder_goals)
        budget_status = get_budget_status_from_tracker()
        daily_walk_status = await get_cached_daily_activity("bike")
        groq_context = get_groq_context_for_narrator()
        
        # Weather-aware logic
        weather = weather_service.get_weather()
        is_appropriate, weather_msg = weather_service.is_walk_appropriate(weather)

        pending_todos = [t for t in todos if not t.get("completed", False)]
        critical_beeminder = [g for g in beeminder_goals if g.get("derail_risk") == "CRITICAL"]
        
        budget_days = budget_status.get("days_remaining", 0)
        summary = f"Active goals: {len(active_goals)}, Pending todos: {len(pending_todos)}, Beeminder goals: {len(beeminder_goals)}, Budget: {budget_days:.1f} days left"
        
        urgent_items = [f"DERAILING: {g['slug']}" for g in critical_beeminder]
        if budget_days <= 1: urgent_items.append(f"BUDGET CRITICAL: {budget_days:.1f} days left")
        elif budget_days <= 2: urgent_items.append(f"BUDGET WARNING: {budget_days:.1f} days left")

        recommendations = []
        if len(pending_todos) > 10: recommendations.append("Consider prioritizing todos - large backlog detected")
        if critical_beeminder: recommendations.append("Address critical Beeminder goals immediately")
        if budget_days <= 2: recommendations.append("Urgent: Focus on highest-value work due to budget constraints")
        
        # Enhanced walk logic: Only recommend if walk needed AND weather/sun is appropriate
        if daily_walk_status.get("status") == "needed":
            if is_appropriate:
                recommendations.append(f"🐾 Priority: {weather_msg} - Walk Boris & Fiona!")
                urgent_items.append("WALK NEEDED: Boris & Fiona")
            else:
                recommendations.append(f"🐕 Walk status: Needed, but {weather_msg}")
        
        if anthropic_cost_tracker:
            recommendations.append("📊 Real-time budget tracking is active via Anthropic Admin API")

        if groq_context.get("groq_tracking", {}).get("needs_action"):
            groq_urgent = groq_context["groq_tracking"].get("urgent_reminder")
            if groq_urgent:
                urgent_items.append(f"GROQ: {groq_urgent}")
                recommendations.append(groq_urgent)

        return {
            "summary": summary, "goals_status": {"total": len(active_goals)},
            "urgent_items": urgent_items, "beeminder_alerts": [e.get("message", "") for e in emergencies[:5]],
            "goal_runway": goal_runway, "budget_status": budget_status, "recommendations": recommendations,
            "daily_walk_status": daily_walk_status, "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to build narrator context: {e}")
        return {"error": f"Failed to build narrator context: {e}"}

@mcp.tool(description="Get Beeminder goal portfolio status with risk assessment.")
async def get_beeminder_status() -> Dict[str, Any]:
    """Get Beeminder goal portfolio status with risk assessment."""
    try:
        goals = await beeminder_client.get_all_goals()
        emergencies = await beeminder_client.get_emergencies()
        return {
            "goals": goals, "emergencies": emergencies,
            "safe_count": len([g for g in goals if g.get("derail_risk") == "SAFE"]),
            "warning_count": len([g for g in goals if g.get("derail_risk") in ["WARNING", "CAUTION"]]),
            "critical_count": len([g for g in goals if g.get("derail_risk") == "CRITICAL"])
        }
    except Exception as e:
        logger.error(f"Failed to fetch Beeminder status: {e}")
        return {"error": f"Failed to fetch Beeminder status: {e}"}

@mcp.tool(description="Get current usage and budget status with days remaining.")
def get_budget_status() -> Dict[str, Any]:
    return get_budget_status_from_tracker()

@mcp.tool(description="Get recent usage sessions.")
def get_recent_usage(limit: int = 10) -> List[Dict[str, Any]]:
    return usage_tracker.get_recent_sessions(limit)

@mcp.tool(description="Record Claude usage session with token counts.")
def record_usage_session(input_tokens: int, output_tokens: int, model: str = "claude-3-5-sonnet-20241022", session_type: str = "interactive", notes: str = "") -> Dict[str, Any]:
    try:
        cost = record_usage(input_tokens, output_tokens, model, session_type, notes)
        return {"recorded": True, "estimated_cost": cost, "updated_status": get_budget_status_from_tracker()}
    except Exception as e:
        logger.error(f"Failed to record usage: {e}")
        return {"error": f"Failed to record usage: {e}"}

@mcp.tool(description="Record Claude Code CLI usage specifically.")
def record_claude_code_usage(input_tokens: int, output_tokens: int, model: str = "claude-3-5-sonnet-20241022", notes: str = "") -> Dict[str, Any]:
    """Specific tool for Claude Code CLI to report its own usage."""
    try:
        cost = record_usage(input_tokens, output_tokens, model, "claude-code", notes)
        return {
            "recorded": True, 
            "estimated_cost": cost, 
            "message": f"Recorded ${cost:.4f} usage for Claude Code session.",
            "updated_status": get_budget_status_from_tracker()
        }
    except Exception as e:
        logger.error(f"Failed to record Claude Code usage: {e}")
        return {"error": str(e)}

@mcp.tool(description="Get real usage data from Anthropic Admin API (organization level).")
async def get_real_anthropic_usage(days: int = 1) -> Dict[str, Any]:
    """Fetch actual usage data from Anthropic organization report."""
    if not anthropic_cost_tracker:
        return {"error": "Anthropic Admin API key not configured or tracker failed to initialize."}
    
    try:
        from datetime import datetime, timedelta, UTC
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=days)
        
        usage = anthropic_cost_tracker.get_usage(start_time, end_time)
        
        # Summarize usage
        total_input = 0
        total_output = 0
        for bucket in usage.get('data', []):
            for result in bucket.get('results', []):
                total_input += result.get('uncached_input_tokens', 0)
                total_input += result.get('cache_read_input_tokens', 0)
                if 'cache_creation' in result:
                    total_input += result['cache_creation'].get('ephemeral_1h_input_tokens', 0)
                total_output += result.get('output_tokens', 0)
        
        # Estimate cost based on Sonnet pricing
        est_cost = (total_input * 3.0 / 1_000_000) + (total_output * 15.0 / 1_000_000)
        
        return {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "estimated_cost": round(est_cost, 4),
            "raw_data": usage
        }
    except Exception as e:
        logger.error(f"Failed to fetch real Anthropic usage: {e}")
        return {"error": str(e)}

@mcp.tool(description="Check for beemergencies and send SMS alerts if critical.")
async def send_beeminder_alert() -> Dict[str, Any]:
    try:
        emergencies = await beeminder_client.get_emergencies()
        critical_emergencies = [e for e in emergencies if e.get("urgency") == "IMMEDIATE"]
        if critical_emergencies and usage_tracker.should_send_alert("beeminder", "critical", cooldown_minutes=90):
            alert_message = f"🚨 BEEMERGENCY: {len(critical_emergencies)} goals need immediate attention!"
            send_sms(alert_message)
            usage_tracker.log_alert("beeminder", "critical", alert_message, f"count: {len(critical_emergencies)}")
            return {"alert_sent": True, "count": len(critical_emergencies)}
        return {"alert_sent": False, "reason": "No critical emergencies or on cooldown"}
    except Exception as e:
        logger.error(f"Failed to send beeminder alert: {e}")
        return {"error": f"Failed to send beeminder alert: {e}"}

@mcp.tool(description="Check if daily activity was logged for a specific goal.")
async def get_daily_activity(goal_slug: str = "bike") -> Dict[str, Any]:
    return await get_cached_daily_activity(goal_slug)

@mcp.tool(description="Get current weather and a recommendation for outdoor activity.")
def get_weather_report() -> Dict[str, Any]:
    """Get current weather and a walk suitability check."""
    weather = weather_service.get_weather()
    is_appropriate, message = weather_service.is_walk_appropriate(weather)
    return {
        "weather": weather,
        "is_appropriate": is_appropriate,
        "recommendation": message
    }

@mcp.tool(description="Add a new goal to the local database.")
def add_goal(title: str, description: str = "", priority: str = "medium", due_date: Optional[str] = None) -> Dict[str, Any]:
    return add_goal_from_tracker(title, description, priority, due_date)

@mcp.tool(description="Mark a goal as completed.")
def complete_goal(goal_id: int) -> Dict[str, Any]:
    return complete_goal_from_tracker(goal_id)

@mcp.tool(description="Manually update budget information.")
def update_budget(remaining_budget: float, total_budget: Optional[float] = None, period_end: Optional[str] = None) -> Dict[str, Any]:
    return usage_tracker.update_budget(remaining_budget, total_budget, period_end)

@mcp.tool(description="Record manual Groq odometer reading with cumulative cost.")
def record_groq_reading(value: float, notes: str = "", month: Optional[str] = None) -> Dict[str, Any]:
    return record_groq_reading_from_tracker(value, notes, month)

@mcp.tool(description="Get Groq odometer status and usage reminders.")
def get_groq_status() -> Dict[str, Any]:
    return get_groq_reminder_status()

@mcp.tool(description="Get Groq odometer context for narrator integration.")
def get_groq_context() -> Dict[str, Any]:
    return get_groq_context_for_narrator()

@mcp.tool(description="Get unified cost status combining Claude budget and Groq usage data.")
async def get_unified_cost_status() -> Dict[str, Any]:
    try:
        from groq_odometer_tracker import _get_tracker
        budget_data = get_budget_status_from_tracker()
        groq_tracker = _get_tracker()
        groq_status = groq_tracker.check_reminder_needs()
        groq_usage = groq_tracker.get_usage_for_virtual_budget()
        return {"claude": budget_data, "groq": {**groq_status, **groq_usage}}
    except Exception as e:
        logger.error(f"Failed to get unified cost status: {e}")
        return {"error": f"Failed to get unified cost status: {e}"}

@mcp.tool(description="Check for needed reminders and send them intelligently.")
async def trigger_reminder_check() -> Dict[str, Any]:
    try:
        check_result = await check_reminder_needed()
        if not check_result.get("should_send"):
            return {"triggered": False, "reason": check_result.get("reason")}
        
        send_result = await send_reminder_message(check_result)
        return {"triggered": True, "check": check_result, "send": send_result}
    except Exception as e:
        logger.error(f"Reminder trigger failed: {e}")
        return {"error": f"Reminder trigger failed: {e}"}

from services.coaching_service import CoachingService

@mcp.tool(description="Get a personalized coaching insight based on momentum and current needs.")
async def get_coaching_insight() -> Dict[str, Any]:
    """Analyze current state and provide a momentum-aware coaching pivot."""
    try:
        # Dependency Injection for the Service
        async def _get_obsidian_context():
            today = datetime.now().strftime("%Y-%m-%d")
            return await obsidian_client.get_daily_note(today)

        service = CoachingService(
            context_provider=get_narrator_context,
            goal_provider=get_cached_beeminder_goals,
            obsidian_provider=_get_obsidian_context
        )
        
        insight = await service.generate_insight()
        return insight.to_dict()
            
    except Exception as e:
        logger.error(f"Failed to generate coaching insight: {e}")
        return {"error": str(e)}

async def check_reminder_needed() -> Dict[str, Any]:
    context = await get_narrator_context()
    current_hour = datetime.now().hour
    budget_status = context.get("budget_status", {})
    remaining_budget = budget_status.get("remaining_budget", 0)
    
    insight = await get_coaching_insight()
    
    walk_needed = context.get("daily_walk_status", {}).get("status") == "needed"
    
    # Logic: Only send walk reminders in the afternoon window
    if 14 <= current_hour <= 17:
        if walk_needed:
             return {"should_send": True, "message": insight.get("message"), "type": "walk_reminder"}
        elif insight.get("momentum") == "high" and current_hour >= 16:
             # Even if walked, if it's late and momentum is high, send a coaching pivot
             return {"should_send": True, "message": insight.get("message"), "type": "momentum_coaching"}
        
    return {"should_send": False, "reason": "Conditions not met or already handled"}

async def send_reminder_message(message_data: Dict[str, Any]) -> Dict[str, Any]:
    message = message_data.get("message")
    msg_type = message_data.get("type")
    
    spam_file = "/tmp/mecris_daily_reminders.log"
    today = str(datetime.now().date())
    if os.path.exists(spam_file):
        with open(spam_file, 'r') as f:
            if f.read().strip() == f"{today}:{msg_type}":
                return {"sent": False, "reason": "Already sent today"}

    delivery_result = smart_send_message(message)
    if delivery_result["sent"]:
        with open(spam_file, 'w') as f:
            f.write(f"{today}:{msg_type}")
    return delivery_result



if __name__ == "__main__":
    mcp.run()
