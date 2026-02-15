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
from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions

from obsidian_client import ObsidianMCPClient
from beeminder_client import BeeminderClient
from usage_tracker import UsageTracker, get_budget_status as get_budget_status_from_tracker, record_usage, update_remaining_budget, get_goals, complete_goal as complete_goal_from_tracker, add_goal as add_goal_from_tracker
from virtual_budget_manager import VirtualBudgetManager
from billing_reconciliation import BillingReconciliation
from groq_odometer_tracker import get_groq_context_for_narrator, get_groq_reminder_status, record_groq_reading as record_groq_reading_from_tracker
from twilio_sender import smart_send_message, send_sms

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
server = Server("mecris")

# Initialize clients
obsidian_client = ObsidianMCPClient()
beeminder_client = BeeminderClient()
usage_tracker = UsageTracker()
virtual_budget_manager = VirtualBudgetManager()
billing_reconciler = BillingReconciliation()

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

@server.tool(description="Get unified strategic context with goals, budget, and recommendations.", input_schema={})
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

@server.tool(description="Get Beeminder goal portfolio status with risk assessment.", input_schema={})
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

@server.tool(description="Get current usage and budget status with days remaining.", input_schema={})
def get_budget_status() -> Dict[str, Any]:
    return get_budget_status_from_tracker()

@server.tool(
    description="Record Claude usage session with token counts.",
    input_schema={
        "type": "object",
        "properties": {
            "input_tokens": {"type": "integer", "description": "Number of input tokens."},
            "output_tokens": {"type": "integer", "description": "Number of output tokens."},
            "model": {"type": "string", "description": "The model used for the session.", "default": "claude-3-5-sonnet-20241022"},
            "session_type": {"type": "string", "description": "Type of session.", "default": "interactive"},
            "notes": {"type": "string", "description": "Additional notes for the session.", "default": ""},
        },
        "required": ["input_tokens", "output_tokens"],
    }
)
def record_usage_session(input_tokens: int, output_tokens: int, model: str = "claude-3-5-sonnet-20241022", session_type: str = "interactive", notes: str = "") -> Dict[str, Any]:
    try:
        cost = record_usage(input_tokens, output_tokens, model, session_type, notes)
        return {"recorded": True, "estimated_cost": cost, "updated_status": get_budget_status_from_tracker()}
    except Exception as e:
        logger.error(f"Failed to record usage: {e}")
        return {"error": f"Failed to record usage: {e}"}

@server.tool(description="Check for beemergencies and send SMS alerts if critical.", input_schema={})
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

@server.tool(
    description="Check if daily activity was logged for a specific goal.",
    input_schema={
        "type": "object",
        "properties": {
            "goal_slug": {"type": "string", "description": "The slug of the goal to check.", "default": "bike"},
        },
    }
)
async def get_daily_activity(goal_slug: str = "bike") -> Dict[str, Any]:
    return await get_cached_daily_activity(goal_slug)

@server.tool(
    description="Add a new goal to the local database.",
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Title of the goal."},
            "description": {"type": "string", "description": "Description of the goal.", "default": ""},
            "priority": {"type": "string", "description": "Priority of the goal.", "default": "medium"},
            "due_date": {"type": "string", "description": "Due date for the goal (YYYY-MM-DD)."},
        },
        "required": ["title"],
    }
)
def add_goal(title: str, description: str = "", priority: str = "medium", due_date: Optional[str] = None) -> Dict[str, Any]:
    return add_goal_from_tracker(title, description, priority, due_date)

@server.tool(
    description="Mark a goal as completed.",
    input_schema={
        "type": "object",
        "properties": {
            "goal_id": {"type": "integer", "description": "The ID of the goal to complete."},
        },
        "required": ["goal_id"],
    }
)
def complete_goal(goal_id: int) -> Dict[str, Any]:
    return complete_goal_from_tracker(goal_id)

@server.tool(
    description="Manually update budget information.",
    input_schema={
        "type": "object",
        "properties": {
            "remaining_budget": {"type": "number", "description": "The remaining budget amount."},
            "total_budget": {"type": "number", "description": "The total budget amount."},
            "period_end": {"type": "string", "description": "The end date of the budget period (YYYY-MM-DD)."},
        },
        "required": ["remaining_budget"],
    }
)
def update_budget(remaining_budget: float, total_budget: Optional[float] = None, period_end: Optional[str] = None) -> Dict[str, Any]:
    return usage_tracker.update_budget(remaining_budget, total_budget, period_end)

@server.tool(
    description="Record manual Groq odometer reading with cumulative cost.",
    input_schema={
        "type": "object",
        "properties": {
            "value": {"type": "number", "description": "The odometer reading value."},
            "notes": {"type": "string", "description": "Notes for the reading.", "default": ""},
            "month": {"type": "string", "description": "The month for the reading (YYYY-MM)."},
        },
        "required": ["value"],
    }
)
def record_groq_reading(value: float, notes: str = "", month: Optional[str] = None) -> Dict[str, Any]:
    return record_groq_reading_from_tracker(value, notes, month)

@server.tool(description="Get Groq odometer status and usage reminders.", input_schema={})
def get_groq_status() -> Dict[str, Any]:
    return get_groq_reminder_status()

@server.tool(description="Get Groq odometer context for narrator integration.", input_schema={})
def get_groq_context() -> Dict[str, Any]:
    return get_groq_context_for_narrator()

@server.tool(description="Get unified cost status combining Claude budget and Groq usage data.", input_schema={})
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

@server.tool(description="Check for needed reminders and send them intelligently.", input_schema={})
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

async def check_reminder_needed() -> Dict[str, Any]:
    context = await get_narrator_context()
    current_hour = datetime.now().hour
    budget_status = context.get("budget_status", {})
    remaining_budget = budget_status.get("remaining_budget", 0)
    tier = "base_mode"
    if remaining_budget > 2.0: tier = "enhanced"
    elif remaining_budget > 0.5: tier = "smart_template"

    walk_needed = context.get("daily_walk_status", {}).get("status") == "needed"
    if walk_needed and 14 <= current_hour <= 17:
        return {"should_send": True, "tier": tier, "message": "🚶‍♂️ Walk reminder!", "type": "walk_reminder"}
        
    return {"should_send": False, "reason": "Conditions not met"}

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



async def main():
    # Note: Starting message must go to stderr to avoid breaking MCP handshake
    logger.error("Starting Mecris MCP Server in stdio mode...")
    try:
        async with stdio_server() as (read_stream, write_stream):
            # Corrected capability retrieval for the latest SDK
            capabilities = server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={}
            )
            logger.error(f"Capabilities: {capabilities}")
            init_options = InitializationOptions(
                server_name="mecris",
                server_version="0.2.0",
                capabilities=capabilities
            )
            await server.run(read_stream, write_stream, init_options)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Mecris MCP stdio server shutting down.")
    except Exception as e:
        logger.error(f"Mcp Stdio Server failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
