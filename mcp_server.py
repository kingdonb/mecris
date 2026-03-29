"""
Mecris MCP Server - Personal LLM Accountability System
This version is refactored to use the MCP Python SDK for stdio communication with the Handler Pattern.
"""

import os
import logging
import asyncio
import sys
from datetime import datetime, timedelta, date, timezone
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
from scripts.clozemaster_scraper import sync_clozemaster_to_beeminder
from services.weather_service import WeatherService
from services.neon_sync_checker import NeonSyncChecker
from services.reminder_service import ReminderService
from services.language_sync_service import LanguageSyncService
from services.review_pump import ReviewPump, ARABIC_POINTS_PER_CARD

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

from scheduler import MecrisScheduler

# Initialize clients
obsidian_client = ObsidianMCPClient()
beeminder_client = BeeminderClient()
neon_checker = NeonSyncChecker()
language_sync_service = LanguageSyncService(beeminder_client)
# Trackers will use DEFAULT_USER_ID from env if not specified
usage_tracker = UsageTracker()
virtual_budget_manager = VirtualBudgetManager()
billing_reconciler = BillingReconciliation()
weather_service = WeatherService()
scheduler = MecrisScheduler() 
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

async def get_cached_daily_activity(goal_slug: str = "bike", user_id: str = None) -> Dict[str, Any]:
    """Get daily activity status with 15-minute cache (refreshed for Cloud sync)."""
    target_user_id = usage_tracker.resolve_user_id(user_id)
    import zoneinfo
    eastern = zoneinfo.ZoneInfo("US/Eastern")
    local_now = datetime.now(eastern)
    today_str = local_now.strftime("%Y-%m-%d")
    
    cache_key = f"{target_user_id}:{goal_slug}:{today_str}"
    
    if cache_key in daily_activity_cache:
        cache_entry = daily_activity_cache[cache_key]
        if local_now < cache_entry["cache_expires"]:
            return {
                "goal_slug": goal_slug, 
                "has_activity_today": cache_entry["has_activity_today"], 
                "status": "completed" if cache_entry["has_activity_today"] else "needed", 
                "source": cache_entry.get("source", "cache"),
                "cached": True
            }

    try:
        # Phase 2: Check Neon Cloud DB first for 'bike' (walks)
        if goal_slug == "bike":
            has_walk = await asyncio.to_thread(neon_checker.has_walk_today, target_user_id)
            if has_walk:
                latest = await asyncio.to_thread(neon_checker.get_latest_walk, target_user_id)
                walk_info = f" (Steps: {latest['step_count']})" if latest else ""
                activity_status = {
                    "goal_slug": goal_slug,
                    "has_activity_today": True,
                    "status": "completed",
                    "check_time": local_now.isoformat(),
                    "message": f"✅ Walk detected in Cloud Sync (Neon){walk_info}",
                    "source": "neon_cloud"
                }
                daily_activity_cache[cache_key] = {
                    "last_check": local_now, 
                    "has_activity_today": True, 
                    "cache_expires": local_now + timedelta(minutes=15),
                    "source": "neon_cloud"
                }
                activity_status["cached"] = False
                return activity_status

        # Fallback to Beeminder (Legacy or non-walk goals)
        activity_status = await beeminder_client.get_daily_activity_status(goal_slug)
        daily_activity_cache[cache_key] = {
            "last_check": local_now, 
            "has_activity_today": activity_status["has_activity_today"], 
            "cache_expires": local_now + timedelta(minutes=15 if goal_slug == "bike" else 60),
            "source": "beeminder"
        }
        activity_status["cached"] = False
        activity_status["source"] = "beeminder"
        return activity_status
    except Exception as e:
        logger.error(f"Failed to fetch daily activity for {goal_slug}: {e}")
        if cache_key in daily_activity_cache:
            return {"goal_slug": goal_slug, "has_activity_today": daily_activity_cache[cache_key]["has_activity_today"], "status": "stale", "error": str(e)}
        return {"goal_slug": goal_slug, "has_activity_today": False, "status": "unknown", "error": str(e)}

# --- Tool Implementations ---

@mcp.tool(description="Get unified strategic context with goals, budget, and recommendations.")
async def get_narrator_context(user_id: str = None) -> Dict[str, Any]:
    """Get unified strategic context with goals, budget, and recommendations."""
    target_user_id = usage_tracker.resolve_user_id(user_id)
    try:
        goals = usage_tracker.get_goals(target_user_id)
        active_goals = [g for g in goals if g.get("status") == "active"]
        try:
            todos = await obsidian_client.get_todos()
        except Exception:
            todos = []
        
        beeminder_goals = await get_cached_beeminder_goals()
        emergencies = await beeminder_client.get_emergencies(beeminder_goals)
        goal_runway = await beeminder_client.get_runway_summary(limit=6, all_goals=beeminder_goals)
        budget_status = await asyncio.to_thread(usage_tracker.get_budget_status, target_user_id)
        daily_walk_status = await get_cached_daily_activity("bike", target_user_id)
        groq_context = await asyncio.to_thread(get_groq_context_for_narrator, target_user_id)

        # Greek backlog boost: check if 7-day review forecast exceeds threshold
        lang_stats = await asyncio.to_thread(neon_checker.get_language_stats, target_user_id)
        greek_backlog_boost = language_sync_service._greek_backlog_active(lang_stats)
        greek_backlog_cards = int(lang_stats.get("greek", lang_stats.get("GREEK", {})).get("next_7_days") or 0)

        # Add latest cloud walk info if available (use to_thread to avoid blocking event loop)
        latest_cloud_walk = await asyncio.to_thread(neon_checker.get_latest_walk, target_user_id)
        if latest_cloud_walk:
            # Convert datetime to ISO string for JSON serialization
            if isinstance(latest_cloud_walk.get("start_time"), datetime):
                latest_cloud_walk["start_time"] = latest_cloud_walk["start_time"].isoformat()
        
        # Fetch user preferences for vacation_mode and time windows
        target_phone = os.getenv('TWILIO_TO_NUMBER')
        vacation_mode = False
        time_window_start = 13
        time_window_end = 17
        
        if target_phone:
            from sms_consent_manager import consent_manager
            user_prefs = await asyncio.to_thread(consent_manager.get_user_preferences, target_phone)
            if user_prefs:
                prefs = user_prefs.get("preferences", {})
                vacation_mode = prefs.get("vacation_mode", False)
                time_window_start = prefs.get("time_window_start", 13)
                time_window_end = prefs.get("time_window_end", 17)

        # Weather-aware logic
        weather = await asyncio.to_thread(weather_service.get_weather)
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
            if vacation_mode:
                recommendations.append("🏃 Personal activity: Recommended (Vacation mode active)")
            elif is_appropriate:
                recommendations.append(f"🐾 Priority: {weather_msg} - Physical Activity Needed!")
                urgent_items.append("WALK NEEDED: Activity Log")
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
            "daily_walk_status": daily_walk_status,
            "latest_cloud_walk": latest_cloud_walk,
            "system_pulse": {
                "running": scheduler.running,
                "is_leader": scheduler.is_leader,
                "process_id": scheduler.process_id
            },
            "vacation_mode": vacation_mode,
            "time_window_start": time_window_start,
            "time_window_end": time_window_end,
            "greek_backlog_boost": greek_backlog_boost,
            "greek_backlog_cards": greek_backlog_cards,
            "last_updated": datetime.now().isoformat()
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
def get_budget_status(user_id: str = None) -> Dict[str, Any]:
    return usage_tracker.get_budget_status(user_id)

@mcp.tool(description="Get recent usage sessions.")
def get_recent_usage(limit: int = 10, user_id: str = None) -> List[Dict[str, Any]]:
    return usage_tracker.get_recent_sessions(limit, user_id)

@mcp.tool(description="Record Claude usage session with token counts.")
def record_usage_session(input_tokens: int, output_tokens: int, model: str = "claude-3-5-haiku-20241022", session_type: str = "interactive", notes: str = "", user_id: str = None) -> Dict[str, Any]:
    try:
        cost = record_usage(input_tokens, output_tokens, model, session_type, notes, user_id)
        return {"recorded": True, "estimated_cost": cost, "updated_status": usage_tracker.get_budget_status(user_id)}
    except Exception as e:
        logger.error(f"Failed to record usage: {e}")
        return {"error": f"Failed to record usage: {e}"}

@mcp.tool(description="Record Claude Code CLI usage specifically.")
def record_claude_code_usage(input_tokens: int, output_tokens: int, model: str = "claude-3- Haiku", notes: str = "", user_id: str = None) -> Dict[str, Any]:
    """Specific tool for Claude Code CLI to report its own usage."""
    try:
        cost = record_usage(input_tokens, output_tokens, model, "claude-code", notes, user_id)
        return {
            "recorded": True, 
            "estimated_cost": cost, 
            "message": f"Recorded ${cost:.4f} usage for Claude Code session.",
            "updated_status": usage_tracker.get_budget_status(user_id)
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
async def get_daily_activity(goal_slug: str = "bike", user_id: str = None) -> Dict[str, Any]:
    return await get_cached_daily_activity(goal_slug, user_id)

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

@mcp.tool(description="Get the full, raw weather status data from the OneCall API.")
def get_weather_full_report() -> Dict[str, Any]:
    """Get the complete, cached weather status including all OneCall data fields."""
    return weather_service.get_weather()

@mcp.tool(description="Force an immediate scrape of Clozemaster and push to Beeminder.")
async def trigger_language_sync() -> Dict[str, Any]:
    """Manually trigger the Clozemaster to Beeminder sync process."""
    result = await language_sync_service.sync_all(dry_run=False)
    if not result.get("success", False):
        return {"error": result.get("error", "Sync failed")}
    return result

@mcp.tool(description="Add a new goal to the local database.")
def add_goal(title: str, description: str = "", priority: str = "medium", due_date: Optional[str] = None, user_id: str = None) -> Dict[str, Any]:
    return usage_tracker.add_goal(title, description, priority, due_date, user_id)

@mcp.tool(description="Mark a goal as completed.")
def complete_goal(goal_id: int, user_id: str = None) -> Dict[str, Any]:
    return usage_tracker.complete_goal(goal_id, user_id)

@mcp.tool(description="Manually update budget information.")
def update_budget(remaining_budget: float, total_budget: Optional[float] = None, period_end: Optional[str] = None, user_id: str = None) -> Dict[str, Any]:
    return usage_tracker.update_budget(remaining_budget, total_budget, period_end, user_id)

@mcp.tool(description="Record manual Groq odometer reading with cumulative cost.")
def record_groq_reading(value: float, notes: str = "", month: Optional[str] = None, user_id: str = None) -> Dict[str, Any]:
    from groq_odometer_tracker import record_groq_reading as record_groq
    return record_groq(value, notes, month, user_id)

@mcp.tool(description="Get Groq odometer status and usage reminders.")
def get_groq_status(user_id: str = None) -> Dict[str, Any]:
    from groq_odometer_tracker import get_groq_reminder_status
    return get_groq_reminder_status(user_id)

@mcp.tool(description="Get Groq odometer context for narrator integration.")
def get_groq_context(user_id: str = None) -> Dict[str, Any]:
    return get_groq_context_for_narrator(user_id)

@mcp.tool(description="Get unified cost status combining Claude budget and Groq usage data.")
async def get_unified_cost_status(user_id: str = None) -> Dict[str, Any]:
    try:
        from groq_odometer_tracker import _get_tracker
        budget_data = await asyncio.to_thread(usage_tracker.get_budget_status, user_id)
        groq_tracker = _get_tracker()
        groq_status = await asyncio.to_thread(groq_tracker.check_reminder_needs, user_id)
        groq_usage = await asyncio.to_thread(groq_tracker.get_usage_for_virtual_budget, user_id)
        return {"claude": budget_data, "groq": {**groq_status, **groq_usage}}
    except Exception as e:
        logger.error(f"Failed to get unified cost status: {e}")
        return {"error": f"Failed to get unified cost status: {e}"}
@mcp.tool(description="Check for needed reminders and send them intelligently.")
async def trigger_reminder_check(user_id: str = None) -> Dict[str, Any]:
    """Manually trigger the reminder logic."""
    target_user_id = user_id or os.getenv("DEFAULT_USER_ID")
    try:
        check_result = await check_reminder_needed(target_user_id)
        if not check_result.get("should_send"):
            return {"triggered": False, "reason": check_result.get("reason")}

        send_result = await send_reminder_message(check_result, target_user_id)
        return {"triggered": True, "check": check_result, "send": send_result}
    except Exception as e:
        logger.error(f"Reminder trigger failed: {e}")
        return {"error": f"Reminder trigger failed: {e}"}

# Link real function to scheduler
scheduler.trigger_reminder_func = trigger_reminder_check


@mcp.tool(description="Sidekiq-like: Enqueue a message to be sent after a delay (in minutes).")
def enqueue_message(message: str, delay_minutes: int, to_number: Optional[str] = None) -> Dict[str, Any]:
    """Sidekiq-like: Enqueue a message to be sent after a delay."""
    return scheduler.enqueue_delayed_message(message, delay_minutes, to_number)

@mcp.tool(description="View the current background job queue and leader status.")
def get_scheduler_queue() -> Dict[str, Any]:
    """View the shared job queue and coordination status."""
    return {
        "process_id": scheduler.process_id,
        "is_leader": scheduler.is_leader,
        "queue": scheduler.get_queue()
    }

from services.coaching_service import CoachingService

@mcp.tool(description="Get a personalized coaching insight based on momentum and current needs.")
async def get_coaching_insight(user_id: str = None) -> Dict[str, Any]:
    """Analyze current state and provide a momentum-aware coaching pivot."""
    try:
        # Dependency Injection for the Service
        async def _get_obsidian_context():
            today = datetime.now().strftime("%Y-%m-%d")
            return await obsidian_client.get_daily_note(today)

        service = CoachingService(
            context_provider=lambda: get_narrator_context(user_id),
            goal_provider=get_cached_beeminder_goals,
            obsidian_provider=_get_obsidian_context
        )
        
        insight = await service.generate_insight()
        return insight.to_dict()
            
    except Exception as e:
        logger.error(f"Failed to generate coaching insight: {e}")
        return {"error": str(e)}

from services.reminder_service import ReminderService
reminder_service = ReminderService(
    context_provider=get_narrator_context,
    coaching_provider=get_coaching_insight
)

@mcp.tool(description="Set the Review Pump intensity multiplier (1.0, 2.0, 4.0, 10.0).")
async def set_review_pump_lever(language: str, multiplier: float, user_id: str = None) -> Dict[str, Any]:
    """Adjust how fast the backlog should be cleared. 1.0=Maintenance, 4.0=Aggressive, 10.0=Blitz."""
    valid_multipliers = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 10.0]
    if multiplier not in valid_multipliers:
        return {"error": f"Invalid multiplier. Must be one of {valid_multipliers}"}

    success = await asyncio.to_thread(neon_checker.update_pump_multiplier, language, multiplier, user_id)
    if success:
        return {"success": True, "message": f"Review Pump for {language} set to {multiplier}x"}
    else:
        return {"error": "Failed to update multiplier in Neon DB"}

@mcp.tool(description="Calculate the language review velocity (Review Pump) required to hit 0 reviews.")
async def get_language_velocity_stats(user_id: str = None) -> Dict[str, Any]:
    """Calculate the velocity required to hit 0 reviews based on current debt, forecasted liabilities, and chosen lever."""
    try:
        # 1. Get stats from Neon (cached from last scraper run) - use to_thread to avoid blocking event loop
        db_stats = await asyncio.to_thread(neon_checker.get_language_stats, user_id)
        if not db_stats:
            # Fallback to scrape if DB is empty
            scraper_data = await sync_clozemaster_to_beeminder(dry_run=True)
            if not scraper_data:
                return {"error": "No language data available"}

            # Map scraper format to internal stats format
            db_stats = {}
            for lang, data in scraper_data.items():
                db_stats[lang] = {
                    "current": data.get("count", 0),
                    "tomorrow": data.get("forecast", {}).get("tomorrow", 0),
                    "multiplier": 1.0
                }

        # 2. Use daily_completions from Neon (numPointsToday) as the flow rate.
        # Previously this fetched Beeminder datapoints for reviewstack/ellinika, but those
        # goals track the current review *backlog* (not completions). Summing backlog
        # snapshots as if they were completions caused the Pump to report "turbulent"
        # whenever the backlog was large — even when zero reviews had been done that day.
        results = {}
        for lang, stats in db_stats.items():
            current_debt = stats.get("current", 0)
            tomorrow_liability = stats.get("tomorrow", 0)
            multiplier = stats.get("multiplier", 1.0)
            
            # Unit Handling:
            # - Greek (ellinika) is tracked in points (goal value ~26k).
            # - Arabic (reviewstack) is tracked in cards (goal value ~2k).
            # - daily_completions from Neon: Python sync stores raw points (numPointsToday);
            #   Rust failover sync pre-converts Arabic to cards before writing. Python is the
            #   primary sync path (Spin cron disabled), so we divide by 12 here to normalize
            #   Arabic to cards. If Rust failover ran last, this double-divides — acceptable
            #   risk until numReviewsToday (direct card count) is confirmed in the API.
            
            unit = "points"
            daily_done = stats.get("daily_completions", 0)
            
            if lang.lower() == "arabic":
                unit = "cards"
                # Heuristic: 1 card is approximately 12 points (average of 8 and 16).
                # This normalizes the points earned into an estimated card count to match current_debt.
                daily_done = int(daily_done / ARABIC_POINTS_PER_CARD)

            pump = ReviewPump(multiplier=multiplier)
            pump_status = pump.get_status(current_debt, tomorrow_liability, daily_done, unit=unit)

            results[lang] = pump_status

        return results

    except Exception as e:
        logger.error(f"Failed to calculate Review Pump stats: {e}")
        return {"error": str(e)}

async def check_reminder_needed(user_id: str = None) -> Dict[str, Any]:
    return await reminder_service.check_reminder_needed(user_id)

async def get_last_sent_time(msg_type: str, user_id: str = None) -> Optional[datetime]:
    target_user_id = usage_tracker.resolve_user_id(user_id)
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        return None
    
    def _fetch():
        import psycopg2
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sent_at FROM message_log WHERE type = %s AND user_id = %s ORDER BY sent_at DESC LIMIT 1", 
                    (msg_type, target_user_id)
                )
                row = cur.fetchone()
                return row[0] if row else None
    try:
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"Failed to fetch last sent time: {e}")
        return None

async def send_reminder_message(message_data: Dict[str, Any], user_id: str = None) -> Dict[str, Any]:
    msg_type = message_data.get("type")
    use_template = message_data.get("template_sid") is not None
    target_user_id = usage_tracker.resolve_user_id(user_id)
    
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        return {"sent": False, "reason": "NEON_DB_URL not configured"}
        
    today = date.today()
    now = datetime.now()
    
    # Cooldown logic is now handled by the ReminderService heuristics.
    # We trust the engine.

    if use_template:
        from twilio_sender import send_whatsapp_template
        template_sid = message_data.get("template_sid")
        variables = message_data.get("variables", {})
        success = send_whatsapp_template(template_sid, variables)
        delivery_result = {
            "sent": success, 
            "method": "whatsapp_template", 
            "template_sid": template_sid
        }
    else:
        message = message_data.get("message") or message_data.get("fallback_message")
        delivery_result = smart_send_message(message)

    if delivery_result["sent"]:
        # Log to Neon
        def _write_log():
            import psycopg2
            with psycopg2.connect(neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO message_log (date, type, sent_at, user_id) VALUES (%s, %s, %s, %s)", (today, msg_type, now, target_user_id))

        try:
            await asyncio.to_thread(_write_log)
        except Exception as e:
            logger.error(f"Failed to log message to Neon: {e}")

    return delivery_result



reminder_service = ReminderService(get_narrator_context, get_coaching_insight, get_last_sent_time)

# ---------------------------------------------------------------------------
# Budget Governor MCP tool (Plan: yebyen/mecris#26)
# ---------------------------------------------------------------------------
from services.budget_governor import BudgetGovernor as _BudgetGovernor

_budget_governor = _BudgetGovernor()

@mcp.tool(description="Get per-bucket LLM spend envelope status and routing recommendation (Budget Governor).")
def get_budget_governor_status() -> Dict[str, Any]:
    """Returns per-bucket consumption, envelope status, and a routing recommendation."""
    return _budget_governor.get_status()

if __name__ == "__main__":
    import sys
    import asyncio
    
    if len(sys.argv) > 1 and sys.argv[1] == "--stdio":
        async def run_stdio():
            scheduler.start()
            await mcp.run_stdio_async()
            scheduler.shutdown()
            
        asyncio.run(run_stdio())
    else:
        # In other modes, mcp.run() might be used, but generally we run via start_server.py for SSE
        mcp.run()
