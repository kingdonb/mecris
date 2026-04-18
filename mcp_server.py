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
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from services.auth_service import get_current_user, is_standalone_mode

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
from services.credentials_manager import credentials_manager
from ghost.presence import get_neon_store, StatusType

# Load environment variables
load_dotenv()

# Configure logging to stderr with ERROR level
logging.basicConfig(
    level=logging.ERROR,
    stream=sys.stderr,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mecris")

async def _record_presence(user_id: str) -> None:
    """Record ACTIVE_HUMAN presence for user_id. No-op when Neon is unavailable."""
    store = get_neon_store()
    if store is None:
        return
    try:
        await asyncio.to_thread(store.upsert, user_id, StatusType.ACTIVE_HUMAN, "mcp_server")
    except Exception as e:
        logger.warning(f"Presence record failed (non-fatal): {e}")


async def _get_presence_status(user_id: str) -> Optional[str]:
    """Return current presence status_type string for user_id, or None if unavailable."""
    store = get_neon_store()
    if store is None:
        return None
    try:
        record = await asyncio.to_thread(store.get, user_id)
        return record.status_type.value if record else None
    except Exception:
        return None


# Initialize the MCP Server
mcp = FastMCP("mecris")

# Create FastAPI app for HTTP endpoints
app = FastAPI(title="Mecris API")

# Add CORS middleware for Web UI development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_authorized_user(user_id: Optional[str] = Depends(get_current_user)):
    """FastAPI Dependency: Enforces authentication and resolves target user ID."""
    mode = os.getenv("MECRIS_MODE", "standalone")
    
    # Cloud Cron Exception (Akamai/Fermyon): Special handling for unauthenticated triggers
    # logic omitted here for brevity but handled in endpoint logic if needed
    
    if user_id:
        return user_id

    if mode == "standalone":
        # In standalone/trusted mode, we allow fallback to the local default user
        resolved_id = credentials_manager.resolve_user_id()
        if resolved_id:
            return resolved_id
    
    # In multi-tenant mode, or if no local user could be resolved: REJECT.
    print(f"AUTH FAILURE: No valid user_id found (mode={mode})", file=sys.stderr)
    raise HTTPException(status_code=401, detail="Authentication Required")

@app.get("/health")
async def health_check():
    # Check Neon connectivity
    neon_active = False
    try:
        import psycopg2
        conn = psycopg2.connect(os.getenv("NEON_DB_URL"))
        conn.close()
        neon_active = True
    except: pass
    
    return {
        "status": "healthy",
        "home_server_active": True,
        "neon_connected": neon_active,
        "leader_pid": scheduler.process_id if scheduler else "unknown",
        "last_seen": datetime.now(timezone.utc).isoformat()
    }

@app.post("/walks")
async def upload_walk(walk_data: Dict[str, Any], user_id: str = Depends(get_authorized_user)):
    try:
        import psycopg2
        neon_url = os.getenv("NEON_DB_URL")
        
        # Encrypt gps_route_points if present and encryption is active
        gps_points = str(walk_data.get("gps_route_points", "0"))
        if gps_points != "0":
            gps_points = usage_tracker.encryption.try_encrypt(gps_points)

        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                # Mirror Rust logic: Insert as 'logging' status
                cur.execute("""
                    INSERT INTO walk_inferences 
                    (user_id, start_time, end_time, step_count, distance_meters, distance_source, confidence_score, gps_route_points, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'logging')
                    ON CONFLICT (user_id, start_time) DO UPDATE SET 
                        end_time = EXCLUDED.end_time, 
                        step_count = EXCLUDED.step_count,
                        distance_meters = EXCLUDED.distance_meters,
                        gps_route_points = EXCLUDED.gps_route_points,
                        status = 'logging'
                """, (
                    user_id,
                    walk_data.get("start_time"),
                    walk_data.get("end_time"),
                    walk_data.get("step_count"),
                    walk_data.get("distance_meters"),
                    walk_data.get("distance_source"),
                    walk_data.get("confidence_score", 0.9),
                    gps_points,
                    'logging'
                ))
        
        # Trigger immediate sync for this user
        asyncio.create_task(_global_walk_sync_job(user_id))
        
        return {"status": "success", "message": "Walk ingested and sync triggered"}
    except Exception as e:
        logger.error(f"Failed to ingest walk: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/languages")
async def get_languages(user_id: str = Depends(get_authorized_user)):
    stats = await asyncio.to_thread(neon_checker.get_language_stats, user_id)
    # Convert to format Android app expects
    lang_list = []
    for name, data in stats.items():
        has_goal = bool(data.get("beeminder_slug"))
        lang_list.append({
            "name": name,
            "current": data.get("current", 0),
            "tomorrow": data.get("tomorrow", 0),
            "next_7_days": data.get("next_7_days", 0),
            "daily_rate": data.get("daily_rate", 0.0),
            "safebuf": data.get("safebuf", 0),
            "derail_risk": data.get("derail_risk", "UNKNOWN"),
            "pump_multiplier": data.get("pump_multiplier", 1.0),
            "has_goal": has_goal
        })

    # Sort: Beeminder-tracked languages first, then untracked (closes kingdonb/mecris#121)
    lang_list.sort(key=lambda x: (not x["has_goal"], x["name"]))

    return {"languages": lang_list}

@app.post("/languages/multiplier")
async def update_multiplier(request: Dict[str, Any], user_id: str = Depends(get_authorized_user)):
    name = request.get("name")
    multiplier = request.get("multiplier")
    
    if not name or multiplier is None:
        raise HTTPException(status_code=400, detail="Missing name or multiplier")
        
    await set_review_pump_lever(name, multiplier, user_id)
    return {"status": "success"}

@app.get("/aggregate-status")
async def get_aggregate_status_endpoint(user_id: str = Depends(get_authorized_user)):
    status = await get_daily_aggregate_status(user_id)
    return status

@app.post("/heartbeat")
async def post_heartbeat(data: Dict[str, Any], user_id: str = Depends(get_authorized_user)):
    role = data.get("role", "android_client")
    process_id = data.get("process_id", "unknown")
    
    # scheduler manages the election table
    await asyncio.to_thread(scheduler._update_heartbeat, role, process_id, user_id)
    return {"status": "success", "mcp_server_active": True}

@app.post("/internal/cloud-sync", status_code=202)
async def trigger_cloud_sync_endpoint(user_id: str = Depends(get_authorized_user)):
    logger.info(f"Android app triggered cloud sync for {user_id}")
    
    # Run the slow sync in a background task
    async def run_sync():
        try:
            await language_sync_service.sync_all(user_id=user_id)
            logger.info(f"Background cloud sync complete for {user_id}")
        except Exception as e:
            logger.error(f"Background cloud sync failed for {user_id}: {e}")

    asyncio.create_task(run_sync())
    
    return {
        "status": "accepted", 
        "message": "Cloud sync started in background. Please check /languages in a few moments for updates."
    }

@app.post("/intelligent-reminder/trigger")
async def trigger_reminder_endpoint(user_id: str = Depends(get_authorized_user)):
    return await trigger_reminder_check(user_id)

@app.get("/narrator/context")
async def narrator_context_endpoint(user_id: str = Depends(get_authorized_user)):
    return await get_narrator_context(user_id)

@app.get("/beeminder/status")
async def beeminder_status_endpoint(user_id: str = Depends(get_authorized_user)):
    return await get_beeminder_status(user_id)

@app.get("/budget/status")
async def budget_status_endpoint(user_id: str = Depends(get_authorized_user)):
    return get_budget_status(user_id)

# Mount the MCP server's ASGI app
# This allows the same process to serve both the MCP protocol (via stdio or SSE) 
# and custom HTTP endpoints.
app.mount("/mcp", mcp.sse_app())

from scheduler import MecrisScheduler, _global_walk_sync_job

# Initialize clients
obsidian_client = ObsidianMCPClient()
default_beeminder_client = BeeminderClient()
neon_checker = NeonSyncChecker()
language_sync_service = LanguageSyncService(default_beeminder_client)
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
# Multi-tenant cache: {user_id: {"data": [...], "cache_expires": ...}}
beeminder_goals_cache: Dict[str, Dict[str, Any]] = {}

def get_user_beeminder_client(user_id: str = None) -> BeeminderClient:
    """Return a BeeminderClient for the specific user."""
    target_user_id = usage_tracker.resolve_user_id(user_id)
    return BeeminderClient(user_id=target_user_id)

async def get_cached_beeminder_goals(user_id: str = None) -> List[Dict[str, Any]]:
    """Get Beeminder goals with 30-minute cache per user."""
    target_user_id = usage_tracker.resolve_user_id(user_id)
    now = datetime.now()
    
    user_cache = beeminder_goals_cache.get(target_user_id, {})
    if ("data" in user_cache and "cache_expires" in user_cache and now < user_cache["cache_expires"]):
        return user_cache["data"]
    
    try:
        client = get_user_beeminder_client(target_user_id)
        goals_data = await client.get_all_goals()
        beeminder_goals_cache[target_user_id] = {
            "data": goals_data, 
            "last_check": now, 
            "cache_expires": now + timedelta(minutes=30)
        }
        return goals_data
    except Exception as e:
        logger.error(f"Failed to fetch Beeminder goals for user {target_user_id}: {e}")
        return user_cache.get("data", [])

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
        client = get_user_beeminder_client(target_user_id)
        activity_status = await client.get_daily_activity_status(goal_slug)
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
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {
            "error": "Authentication Required",
            "instruction": "Please run `mecris login` in your terminal to authenticate."
        }
    await _record_presence(target_user_id)
    try:
        goals = usage_tracker.get_goals(target_user_id)
        active_goals = [g for g in goals if g.get("status") == "active"]
        try:
            todos = await obsidian_client.get_todos()
        except Exception:
            todos = []
        
        beeminder_goals = await get_cached_beeminder_goals(target_user_id)
        client = get_user_beeminder_client(target_user_id)
        emergencies = await client.get_emergencies(beeminder_goals)
        goal_runway = await client.get_runway_summary(limit=6, all_goals=beeminder_goals)
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

        # Majesty Cake: surface aggregate daily goal status early for discoverability (kingdonb/mecris#170)
        try:
            daily_aggregate = await get_daily_aggregate_status(target_user_id)
            if not daily_aggregate.get("error"):
                if daily_aggregate.get("all_clear"):
                    recommendations.insert(0, f"🎂 Majesty Cake! All daily goals complete ({daily_aggregate.get('score', '?/?')})")
                else:
                    score = daily_aggregate.get("score", "?/?")
                    recommendations.append(f"🎯 Daily goals progress: {score} — keep going!")
        except Exception as e:
            logger.error(f"get_narrator_context: daily aggregate status failed: {e}")
            daily_aggregate = {"error": str(e)}

        # Greek Stack Vitality Coaching (kingdonb/mecris#129)
        if greek_backlog_boost:
            recommendations.append(f"🏺 Greek Overload: {greek_backlog_cards} cards pending. Focus on REVIEWS to clear the backlog.")
        elif greek_backlog_cards < 100 and not vacation_mode:
            recommendations.append("🏺 Greek Pipe Thinning: Future reviews are low. Consider PLAYING new cards to build future momentum.")

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
            "daily_aggregate_status": daily_aggregate,
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
            "budget_governor": _budget_governor.get_narrator_summary(),
            "presence_status": await _get_presence_status(target_user_id),
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to build narrator context: {e}")
        return {"error": f"Failed to build narrator context: {e}"}

@mcp.tool(description="Get Beeminder goal portfolio status with risk assessment.")
async def get_beeminder_status(user_id: str = None) -> Dict[str, Any]:
    """Get Beeminder goal portfolio status with risk assessment."""
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    try:
        client = get_user_beeminder_client(target_user_id)
        goals = await client.get_all_goals()
        emergencies = await client.get_emergencies()
        return {
            "goals": goals, "emergencies": emergencies,
            "safe_count": len([g for g in goals if g.get("derail_risk") == "SAFE"]),
            "warning_count": len([g for g in goals if g.get("derail_risk") in ["WARNING", "CAUTION"]]),
            "critical_count": len([g for g in goals if g.get("derail_risk") == "CRITICAL"])
        }
    except Exception as e:
        logger.error(f"Failed to fetch Beeminder status: {e}")
        return {"error": f"Failed to fetch Beeminder status: {e}"}

def resolve_target_user(user_id: Optional[str]) -> Optional[str]:
    """Resolve user ID and enforce authentication if required."""
    return credentials_manager.resolve_user_id(user_id)

@mcp.tool(description="Get current usage and budget status with days remaining.")
def get_budget_status(user_id: str = None) -> Dict[str, Any]:
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    return usage_tracker.get_budget_status(target_user_id)

@mcp.tool(description="Get recent usage sessions.")
def get_recent_usage(limit: int = 10, user_id: str = None) -> List[Dict[str, Any]]:
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return [{"error": "Authentication Required"}]
    return usage_tracker.get_recent_sessions(limit, target_user_id)

@mcp.tool(description="Record Claude usage session with token counts.")
def record_usage_session(input_tokens: int, output_tokens: int, model: str = "claude-3-5-haiku-20241022", session_type: str = "interactive", notes: str = "", user_id: str = None) -> Dict[str, Any]:
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    try:
        cost = record_usage(input_tokens, output_tokens, model, session_type, notes, target_user_id)
        _record_governor_spend(model, cost)
        return {"recorded": True, "estimated_cost": cost, "updated_status": usage_tracker.get_budget_status(target_user_id)}
    except Exception as e:
        logger.error(f"Failed to record usage: {e}")
        return {"error": f"Failed to record usage: {e}"}

@mcp.tool(description="Record Claude Code CLI usage specifically.")
def record_claude_code_usage(input_tokens: int, output_tokens: int, model: str = "claude-3- Haiku", notes: str = "", user_id: str = None) -> Dict[str, Any]:
    """Specific tool for Claude Code CLI to report its own usage."""
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    try:
        cost = record_usage(input_tokens, output_tokens, model, "claude-code", notes, target_user_id)
        _record_governor_spend(model, cost)
        return {
            "recorded": True, 
            "estimated_cost": cost, 
            "message": f"Recorded ${cost:.4f} usage for Claude Code session.",
            "updated_status": usage_tracker.get_budget_status(target_user_id)
        }
    except Exception as e:
        logger.error(f"Failed to record Claude Code usage: {e}")
        return {"error": str(e)}

def _record_governor_spend(model: str, cost: float):
    """Internal helper to route spend to the correct BudgetGovernor bucket."""
    bucket = "anthropic_api" # Default
    m_lower = model.lower()
    if "gemini" in m_lower:
        bucket = "gemini"
    elif "groq" in m_lower:
        bucket = "groq"
    elif os.getenv("ANTHROPIC_BASE_URL") and "helix" in os.getenv("ANTHROPIC_BASE_URL").lower():
        bucket = "helix"
    
    try:
        _budget_governor.record_spend(bucket, cost)
    except Exception as e:
        logger.warning(f"BudgetGovernor: Failed to record spend for {bucket}: {e}")

@mcp.tool(description="Get real usage data from Anthropic Admin API (organization level).")
async def get_real_anthropic_usage(days: int = 1) -> Dict[str, Any]:
    """Fetch actual usage data from Anthropic organization report."""
    guard = _budget_governor.budget_gate("anthropic_api")
    if guard and guard.get("budget_halted"):
        return guard
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
async def send_beeminder_alert(user_id: str = None) -> Dict[str, Any]:
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    try:
        client = get_user_beeminder_client(target_user_id)
        emergencies = await client.get_emergencies()
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
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    return await get_cached_daily_activity(goal_slug, target_user_id)

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
    guard = _budget_governor.budget_gate("anthropic_api")
    if guard and guard.get("budget_halted"):
        return guard
    result = await language_sync_service.sync_all(dry_run=False)
    if not result.get("success", False):
        return {"error": result.get("error", "Sync failed")}
    return result

@mcp.tool(description="Add a new goal to the local database.")
def add_goal(title: str, description: str = "", priority: str = "medium", due_date: Optional[str] = None, user_id: str = None) -> Dict[str, Any]:
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    return usage_tracker.add_goal(title, description, priority, due_date, target_user_id)

@mcp.tool(description="Mark a goal as completed.")
def complete_goal(goal_id: int, user_id: str = None) -> Dict[str, Any]:
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    return usage_tracker.complete_goal(goal_id, target_user_id)

@mcp.tool(description="Manually update budget information.")
def update_budget(remaining_budget: float, total_budget: Optional[float] = None, period_end: Optional[str] = None, user_id: str = None) -> Dict[str, Any]:
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    return usage_tracker.update_budget(remaining_budget, total_budget, period_end, target_user_id)

@mcp.tool(description="Record manual Groq odometer reading with cumulative cost.")
async def record_groq_reading(value: float, notes: str = "", month: Optional[str] = None, user_id: str = None) -> Dict[str, Any]:
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    
    # Record locally in Neon first
    result = record_groq_reading_from_tracker(value, notes, month, target_user_id)
    
    if result.get("recorded"):
        # Sync to Beeminder groqspend goal
        try:
            # 1. Check goal start date restriction
            GROQSPEND_START_DATE = "2026-04-13"
            
            # Use the timestamp from the result
            import zoneinfo
            eastern = zoneinfo.ZoneInfo("US/Eastern")
            
            if "timestamp" in result:
                # result["timestamp"] is ISO format from groq_odometer_tracker
                ts_str = result["timestamp"]
                # If it doesn't have TZ info, assume it's UTC or Local? 
                # groq_odometer_tracker uses datetime.now() (naive local) or historical_date (naive)
                # To be safe, let's treat it as naive and attach system local if it's missing
                record_dt = datetime.fromisoformat(ts_str)
                if record_dt.tzinfo is None:
                    # Treat naive as UTC for consistent mapping if coming from DB, 
                    # but groq_tracker uses .now() which is local.
                    # Best to just use the date part if it's an odometer.
                    record_dt = record_dt.replace(tzinfo=timezone.utc)
            else:
                record_dt = datetime.now(timezone.utc)
            
            daystamp = record_dt.astimezone(eastern).strftime("%Y%m%d")
            
            if daystamp < GROQSPEND_START_DATE.replace("-", ""):
                logger.info(f"Skipping Beeminder sync for {daystamp}: before goal start date {GROQSPEND_START_DATE}")
                return result

            # 2. Initialize Beeminder client
            bm_client = get_user_beeminder_client(target_user_id)
            goal_slug = "groqspend"
            
            # 3. Handle @TARE reset if detected
            if result.get("reset_detected"):
                tare_comment = f"@TARE reset for {result.get('month', 'new month')} Transition"
                await bm_client.add_datapoint(goal_slug, 0.0, comment=tare_comment, daystamp=daystamp)
                logger.info(f"Sent @TARE datapoint to Beeminder for {goal_slug}")

            # 4. Push the actual reading
            reading_comment = notes if notes else f"Manual update: {result.get('month', 'current month')} spend"
            await bm_client.add_datapoint(goal_slug, value, comment=reading_comment, daystamp=daystamp)
            logger.info(f"Sent reading {value} to Beeminder goal {goal_slug}")
            
            result["beeminder_sync"] = "success"
        except Exception as e:
            logger.error(f"Failed to sync Groq reading to Beeminder: {e}")
            result["beeminder_sync"] = f"failed: {str(e)}"
            
    return result

@mcp.tool(description="Get Groq odometer status and usage reminders.")
def get_groq_status(user_id: str = None) -> Dict[str, Any]:
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    from groq_odometer_tracker import get_groq_reminder_status
    return get_groq_reminder_status(target_user_id)

@mcp.tool(description="Get Groq odometer context for narrator integration.")
def get_groq_context(user_id: str = None) -> Dict[str, Any]:
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    return get_groq_context_for_narrator(target_user_id)

@mcp.tool(description="Get unified cost status combining Claude budget and Groq usage data.")
async def get_unified_cost_status(user_id: str = None) -> Dict[str, Any]:
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    try:
        from groq_odometer_tracker import _get_tracker
        budget_data = await asyncio.to_thread(usage_tracker.get_budget_status, target_user_id)
        groq_tracker = _get_tracker()
        groq_status = await asyncio.to_thread(groq_tracker.check_reminder_needs, target_user_id)
        groq_usage = await asyncio.to_thread(groq_tracker.get_usage_for_virtual_budget, target_user_id)
        return {"claude": budget_data, "groq": {**groq_status, **groq_usage}}
    except Exception as e:
        logger.error(f"Failed to get unified cost status: {e}")
        return {"error": f"Failed to get unified cost status: {e}"}

@mcp.tool(description="Check for needed reminders and send them intelligently.")
async def trigger_reminder_check(user_id: str = None, apply_fuzz: bool = False) -> Dict[str, Any]:
    """Manually trigger the reminder logic. If apply_fuzz is True, delays the actual check/send by a random interval."""
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required. Run `mecris login`."}
    try:
        check_result = await check_reminder_needed(target_user_id)
        if not check_result.get("should_send"):
            return {"triggered": False, "reason": check_result.get("reason")}

        # If we want to fuzz the delivery time and this is the initial background check
        if apply_fuzz:
            import random
            from datetime import datetime, timedelta, timezone
            from apscheduler.triggers.date import DateTrigger
            
            # Fuzz between 3 and 25 minutes to break up exact 2-hour formulas
            fuzz_minutes = random.randint(3, 25)
            run_time = datetime.now(timezone.utc) + timedelta(minutes=fuzz_minutes)
            job_id = f"fuzzed_reminder_{int(run_time.timestamp())}"
            
            # Enqueue a one-off job to actually send the reminder after the fuzz delay
            scheduler.scheduler.add_job(
                trigger_reminder_check,
                trigger=DateTrigger(run_date=run_time),
                args=[target_user_id, False],
                id=job_id
            )
            logger.info(f"Fuzzed reminder scheduled for {fuzz_minutes} minutes from now (Job: {job_id})")
            return {"triggered": False, "reason": f"Fuzzed for {fuzz_minutes} minutes"}

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

from services.health_checker import HealthChecker as _HealthChecker
_health_checker = _HealthChecker()

@mcp.tool(description="Get unified health status for all registered system processes (Python MCP, Android client, Spin cloud) from the scheduler_election table.")
async def get_system_health(user_id: str = None) -> Dict[str, Any]:
    """Read the scheduler_election table and return active/stale status for every registered process."""
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    result = await asyncio.to_thread(_health_checker.get_system_health, target_user_id)
    if "error" not in result:
        result["leader_process_id"] = scheduler.process_id
        result["is_leader"] = scheduler.is_leader
    return result

from services.coaching_service import CoachingService

@mcp.tool(description="Get a personalized coaching insight based on momentum and current needs.")
async def get_coaching_insight(user_id: str = None) -> Dict[str, Any]:
    """Analyze current state and provide a momentum-aware coaching pivot."""
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    guard = _budget_governor.budget_gate("anthropic_api")
    if guard and guard.get("budget_halted"):
        return guard
    try:
        # Dependency Injection for the Service
        async def _get_obsidian_context():
            today = datetime.now().strftime("%Y-%m-%d")
            return await obsidian_client.get_daily_note(today)

        service = CoachingService(
            context_provider=lambda: get_narrator_context(target_user_id),
            goal_provider=get_cached_beeminder_goals,
            obsidian_provider=_get_obsidian_context
        )
        
        insight = await service.generate_insight()
        return insight.to_dict()
            
    except Exception as e:
        logger.error(f"Failed to generate coaching insight: {e}")
        return {"error": str(e)}

@mcp.tool(description="Set the Review Pump intensity multiplier (1.0, 2.0, 4.0, 10.0).")
async def set_review_pump_lever(language: str, multiplier: float, user_id: str = None) -> Dict[str, Any]:
    """Adjust how fast the backlog should be cleared. 1.0=Maintenance, 4.0=Aggressive, 10.0=Blitz."""
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    valid_multipliers = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 10.0]
    if multiplier not in valid_multipliers:
        return {"error": f"Invalid multiplier. Must be one of {valid_multipliers}"}

    success = await asyncio.to_thread(neon_checker.update_pump_multiplier, language, multiplier, target_user_id)
    if success:
        return {"success": True, "message": f"Review Pump for {language} set to {multiplier}x"}
    else:
        return {"error": "Failed to update multiplier in Neon DB"}

@mcp.tool(description="Calculate the language review velocity (Review Pump) required to hit 0 reviews.")
async def get_language_velocity_stats(user_id: str = None) -> Dict[str, Any]:
    """Calculate the velocity required to hit 0 reviews based on current debt, forecasted liabilities, and chosen lever."""
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    try:
        # 1. Get stats from Neon (cached from last scraper run) - use to_thread to avoid blocking event loop
        db_stats = await asyncio.to_thread(neon_checker.get_language_stats, target_user_id)
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
            # - daily_completions from Neon: 
            #   - Python sync now stores actual card count (cards_today) for Arabic if found.
            #   - Fallback is raw points (numPointsToday).
            #   - We divide by 16 only if the value looks like points (e.g. > 500) to normalize.
            
            unit = "points"
            daily_done = stats.get("daily_completions", 0)
            
            if lang.lower() == "arabic":
                unit = "cards"
                # If daily_done is very high, it's likely raw points and needs normalization.
                # Actual card counts for a single day are typically < 500.
                if daily_done > 500:
                    daily_done = int(daily_done / ARABIC_POINTS_PER_CARD)

            pump = ReviewPump(multiplier=multiplier)
            pump_status = pump.get_status(current_debt, tomorrow_liability, daily_done, unit=unit)
            
            # Surface safebuf (lead time) from DB
            pump_status["safebuf"] = stats.get("safebuf", 0)
            
            # Unit/Goal Classification:
            # - Arabic: Has a "Reviewstack" goal (explicitly tracked/synced)
            # - Greek: Has a "Canonical" points goal (autodata, no sync needed)
            # - Others (Lithuanian, etc.): Truly unplanned debt
            
            if lang.lower() == "greek":
                pump_status["priority_boost"] = True
                pump_status["lever_name"] = f"Canonical ({pump_status['lever_name']})"
            elif not stats.get("beeminder_slug") and lang.lower() != "arabic":
                # This language is in the pile but has no Beeminder accountability plan yet.
                pump_status["goal_met"] = True # Effectively deprioritize unplanned goals
                pump_status["lever_name"] = "No Goal (Unplanned)"
            
            results[lang] = pump_status

        # 3. Sort results: 
        # - Priority boosted goals (GREEK) first if not met
        # - Then unmet goals
        # - Then by target_flow_rate descending
        sorted_items = sorted(
            results.items(),
            key=lambda x: (
                not (x[1].get("priority_boost") and not x[1]["goal_met"]),
                x[1]["goal_met"], 
                -x[1]["target_flow_rate"]
            )
        )
        
        from collections import OrderedDict
        return OrderedDict(sorted_items)

    except Exception as e:
        logger.error(f"Failed to calculate Review Pump stats: {e}")
        return {"error": str(e)}

async def check_reminder_needed(user_id: str = None) -> Dict[str, Any]:
    return await reminder_service.check_reminder_needed(user_id)

async def get_last_sent_time(msg_type: Optional[str] = None, user_id: str = None) -> Optional[datetime]:
    target_user_id = usage_tracker.resolve_user_id(user_id)
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        return None
    
    def _fetch():
        import psycopg2
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                if msg_type:
                    cur.execute(
                        "SELECT sent_at FROM message_log WHERE type = %s AND user_id = %s ORDER BY sent_at DESC LIMIT 1", 
                        (msg_type, target_user_id)
                    )
                else:
                    cur.execute(
                        "SELECT sent_at FROM message_log WHERE user_id = %s ORDER BY sent_at DESC LIMIT 1", 
                        (target_user_id,)
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

    message = message_data.get("message") or message_data.get("fallback_message")
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
        delivery_result = smart_send_message(message)

    # Log to Neon, regardless of success or failure
    status_val = "sent" if delivery_result.get("sent") else "failed"
    error_val = None if delivery_result.get("sent") else "Failed to send (check twilio_sender logs)"
    
    # Encrypt PII fields (error_msg, content) before storing
    encrypted_content = usage_tracker.encryption.try_encrypt(message)
    error_val = usage_tracker.encryption.try_encrypt(error_val)
    
    def _write_log():
        import psycopg2
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        "INSERT INTO message_log (date, type, sent_at, user_id, status, error_msg, content) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                        (today, msg_type, now, target_user_id, status_val, error_val, encrypted_content)
                    )
                except psycopg2.errors.UndefinedColumn:
                    # Fallback if schema wasn't migrated
                    conn.rollback()
                    cur.execute(
                        "INSERT INTO message_log (date, type, sent_at, user_id) VALUES (%s, %s, %s, %s)", 
                        (today, msg_type, now, target_user_id)
                    )

    try:
        await asyncio.to_thread(_write_log)
    except Exception as e:
        logger.error(f"Failed to log message to Neon: {e}")

    return delivery_result



async def get_arabic_skip_count(user_id: str = None) -> int:
    """Return the number of Arabic reminders sent in the last 24h (skip count proxy).

    Used as skip_count_provider for ReminderService Phase 3 escalation.
    Returns 0 if NEON_DB_URL is not configured or on any DB error.
    """
    from services.arabic_skip_counter import count_arabic_reminders
    target_user_id = usage_tracker.resolve_user_id(user_id)
    neon_url = os.getenv("NEON_DB_URL", "")
    if not neon_url:
        return 0
    return await asyncio.to_thread(count_arabic_reminders, neon_url, target_user_id)


reminder_service = ReminderService(get_narrator_context, get_coaching_insight, get_last_sent_time, velocity_provider=get_language_velocity_stats, skip_count_provider=get_arabic_skip_count)

# ---------------------------------------------------------------------------
# Budget Governor MCP tool (Plan: yebyen/mecris#26)
# ---------------------------------------------------------------------------
from services.budget_governor import BudgetGovernor as _BudgetGovernor

_budget_governor = _BudgetGovernor(spend_log_path="mecris_spend_log.json")

@mcp.tool(description="Get per-bucket LLM spend envelope status and routing recommendation (Budget Governor).")
def get_budget_governor_status() -> Dict[str, Any]:
    """Returns per-bucket consumption, envelope status, and a routing recommendation."""
    return _budget_governor.get_status()

def get_modality_status(role: str, mins: float) -> str:
    """Determine healthy/degraded/offline status based on heartbeat age (minutes)."""
    if role == "leader":
        if mins < 2: return "healthy"
        if mins < 5: return "degraded"
        return "offline"
    elif role == "android_client":
        if mins < 20: return "healthy"
        if mins < 60: return "degraded"
        return "offline"
    elif role == "akamai_functions":
        if mins < 135: return "healthy"
        if mins < 250: return "degraded"
        return "offline"
    elif role == "fermyon_cloud":
        if mins < 5: return "reactive"
        if mins < 15: return "degraded"
        return "unknown"
    elif role == "unknown_cloud":
        # Handle cases where provider variable is missing but cloud is active
        if mins < 135: return "healthy"
        if mins < 250: return "degraded"
        return "offline"
    return "unknown"

async def fetch_system_pulse(user_id: str) -> Dict[str, Any]:
    """Fetch recent heartbeats from scheduler_election and return formatted pulse modalities."""
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        return {"modalities": []}

    target_user_id = usage_tracker.resolve_user_id(user_id)

    def _query():
        import psycopg2
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT role, heartbeat, 
                           EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - heartbeat)) / 60 AS minutes_since
                    FROM scheduler_election
                    WHERE user_id = %s OR user_id IS NULL
                    ORDER BY heartbeat DESC
                """, (target_user_id,))
                return cur.fetchall()

    try:
        rows = await asyncio.to_thread(_query)
        modalities = []
        for role, heartbeat, mins_since in rows:
            # Skip only unknown ghosts
            if role == "unknown_cloud":
                continue

            mins = float(mins_since or 9999)
            
            # Map machine names to human-friendly display names (Neural Link aesthetic)
            if role == "leader": display_role = "MCP SERVER"
            elif role == "akamai_functions": display_role = "AKAMAI FUNCTIONS"
            elif role == "fermyon_cloud": display_role = "FERMYON CLOUD"
            elif role == "android_client": display_role = "ANDROID CLIENT"
            else: display_role = role.replace('_', ' ').upper()

            modalities.append({
                "role": display_role,
                "status": get_modality_status(role, mins),
                "last_seen": heartbeat.isoformat() if heartbeat else "never",
                "minutes_since": int(mins)
            })
        return {"modalities": modalities}
    except Exception as e:
        logger.error(f"fetch_system_pulse failed: {e}")
        return {"modalities": []}

@mcp.tool(description="Get unified daily goal completion status for the Majesty Cake widget (kingdonb/mecris#170). Returns X/Y goals satisfied and all_clear flag.")
async def get_daily_aggregate_status(user_id: str = None) -> Dict[str, Any]:
    """Returns aggregated daily goal completion: daily walk (>=2000 steps), Arabic review pump, Greek review pump."""
    target_user_id = resolve_target_user(user_id)
    if not target_user_id:
        return {"error": "Authentication Required"}
    goals = []

    # Goal 1: Daily Walk (>=2000 steps via Neon or Beeminder)
    try:
        walk_status = await get_cached_daily_activity("bike", target_user_id)
        goals.append({
            "name": "daily_walk",
            "label": "Daily Walk (2000 steps)",
            "satisfied": bool(walk_status.get("has_activity_today", False)),
            "source": walk_status.get("source", "unknown"),
        })
    except Exception as e:
        logger.error(f"get_daily_aggregate_status: walk check failed: {e}")
        goals.append({"name": "daily_walk", "label": "Daily Walk (2000 steps)", "satisfied": False, "error": str(e)})

    # Goals 2 & 3: Arabic and Greek Review Pump (goal_met from velocity stats)
    try:
        lang_stats = await get_language_velocity_stats(target_user_id)
        for lang_key, label in [("arabic", "Arabic Review Pump"), ("greek", "Greek Review Pump")]:
            stat = next((v for k, v in lang_stats.items() if isinstance(v, dict) and k.lower() == lang_key), None)
            if stat:
                goals.append({
                    "name": f"{lang_key}_review",
                    "label": label,
                    "satisfied": bool(stat.get("goal_met", False)),
                    "status": stat.get("status", "unknown"),
                })
            else:
                goals.append({"name": f"{lang_key}_review", "label": label, "satisfied": False, "error": "no data"})
    except Exception as e:
        logger.error(f"get_daily_aggregate_status: language stats failed: {e}")
        for lang_key, label in [("arabic", "Arabic Review Pump"), ("greek", "Greek Review Pump")]:
            goals.append({"name": f"{lang_key}_review", "label": label, "satisfied": False, "error": str(e)})

    system_pulse = await fetch_system_pulse(target_user_id)

    # Fetch budget and distance for odometers
    budget_status = await asyncio.to_thread(usage_tracker.get_budget_status, target_user_id)
    latest_walk = await asyncio.to_thread(neon_checker.get_latest_walk, target_user_id)
    
    today_distance_miles = 0.0
    if latest_walk:
        # Check if walk is from today
        walk_start = latest_walk.get("start_time")
        if isinstance(walk_start, datetime) and walk_start.date() == date.today():
            meters = float(latest_walk.get("distance_meters") or 0)
            today_distance_miles = meters * 0.000621371

    satisfied_count = sum(1 for g in goals if g["satisfied"])
    total_count = len(goals)
    return {
        "goals": goals,
        "satisfied_count": satisfied_count,
        "total_count": total_count,
        "all_clear": satisfied_count == total_count,
        "score": f"{satisfied_count}/{total_count}",
        "components": {
            "walk": next((g["satisfied"] for g in goals if g["name"] == "daily_walk"), False),
            "arabic": next((g["satisfied"] for g in goals if g["name"] == "arabic_review"), False),
            "greek": next((g["satisfied"] for g in goals if g["name"] == "greek_review"), False)
        },
        "budget_remaining": budget_status.get("remaining_budget", 0),
        "today_distance_miles": today_distance_miles,
        "system_pulse": system_pulse
    }

@mcp.tool(description="GDPR right-to-erasure: permanently delete all data for a user. Removes token_bank first (no CASCADE), then users row (CASCADE deletes walk_inferences, language_stats, goals, message_log, usage_sessions, autonomous_turns, budget_tracking).")
def delete_user_data(user_id: str = None) -> Dict[str, Any]:
    target_user_id = usage_tracker.resolve_user_id(user_id)
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        return {"deleted": False, "error": "NEON_DB_URL not configured"}

    def _delete():
        import psycopg2
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pocket_id_sub FROM users WHERE pocket_id_sub = %s",
                    (target_user_id,)
                )
                if cur.fetchone() is None:
                    return {"deleted": False, "error": f"User not found: {target_user_id}"}
                cur.execute("DELETE FROM token_bank WHERE user_id = %s", (target_user_id,))
                cur.execute("DELETE FROM users WHERE pocket_id_sub = %s", (target_user_id,))
                return {"deleted": True, "user_id": target_user_id}

    try:
        return _delete()
    except Exception as e:
        logger.error(f"delete_user_data failed: {e}")
        return {"deleted": False, "error": str(e)}


@mcp.tool(description="GDPR data portability: export all data for a user as structured JSON. Returns rows from users, language_stats, budget_tracking, token_bank, walk_inferences, and message_log tables.")
def export_user_data(user_id: str = None) -> Dict[str, Any]:
    target_user_id = usage_tracker.resolve_user_id(user_id)
    neon_url = os.getenv("NEON_DB_URL")
    if not neon_url:
        return {"exported": False, "error": "NEON_DB_URL not configured"}

    def _rows(cur, table: str, col: str) -> list:
        cur.execute(f"SELECT * FROM {table} WHERE {col} = %s", (target_user_id,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _export():
        import psycopg2
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM users WHERE pocket_id_sub = %s",
                    (target_user_id,)
                )
                cols = [d[0] for d in cur.description]
                user_rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                if not user_rows:
                    return {"exported": False, "error": f"User not found: {target_user_id}"}
                return {
                    "exported": True,
                    "user_id": target_user_id,
                    "data": {
                        "users": user_rows,
                        "language_stats": _rows(cur, "language_stats", "user_id"),
                        "budget_tracking": _rows(cur, "budget_tracking", "user_id"),
                        "token_bank": _rows(cur, "token_bank", "user_id"),
                        "walk_inferences": _rows(cur, "walk_inferences", "user_id"),
                        "message_log": _rows(cur, "message_log", "user_id"),
                    }
                }

    try:
        return _export()
    except Exception as e:
        logger.error(f"export_user_data failed: {e}")
        return {"exported": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    import asyncio
    import uvicorn
    import threading

    use_stdio = "--stdio" in sys.argv
    use_http = "--http" in sys.argv

    def run_http():
        print("Starting Mecris API on http://localhost:8000", file=sys.stderr)
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")

    if use_http:
        # Start HTTP server in a background thread
        http_thread = threading.Thread(target=run_http, daemon=True)
        http_thread.start()

    if use_stdio:
        async def run_stdio():
            scheduler.start()
            try:
                await mcp.run_stdio_async()
            finally:
                scheduler.shutdown()
            
        asyncio.run(run_stdio())
    elif use_http:
        # If ONLY http was requested, we need to keep the main thread alive
        scheduler.start()
        try:
            # Since uvicorn.run is blocking, we can just run it in the main thread here
            run_http()
        finally:
            scheduler.shutdown()
    else:
        # Default fallback
        mcp.run()
