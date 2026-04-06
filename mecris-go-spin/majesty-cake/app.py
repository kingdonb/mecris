"""
Majesty Cake WASM component — app.py (Daily Aggregate Status)

HTTP handler: GET /internal/majesty-cake-status?user_id=<id>
Reads neon_db_url from Spin variables.
Returns JSON mirroring get_daily_aggregate_status from mcp_server.py.

Logic:
1. Walk: >= 2000 steps today in walk_inferences.
2. Arabic/Greek: goal_met calculated from language_stats (ReviewPump logic).

Implementation: componentize-py + spin_sdk HTTP incoming-handler.
"""

import base64
import json
import logging
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import zoneinfo

logger = logging.getLogger("mecris.majesty_cake_component")

# US/Eastern is the canonical timezone for Mecris day boundaries
EASTERN = zoneinfo.ZoneInfo("America/New_York")

_WALK_SQL = (
    "SELECT COUNT(*) FROM walk_inferences "
    "WHERE (start_time::TIMESTAMPTZ AT TIME ZONE 'US/Eastern')::DATE = (CURRENT_TIMESTAMP AT TIME ZONE 'US/Eastern')::DATE "
    "AND CAST(step_count AS INTEGER) >= 2000 "
    "AND user_id = $1"
)

_LANG_SQL = (
    "SELECT language_name, current_reviews, tomorrow_reviews, pump_multiplier::FLOAT8, daily_completions "
    "FROM language_stats WHERE user_id = $1"
)

def _http_url_and_auth(neon_url: str) -> tuple:
    parsed = urlparse(neon_url)
    host = parsed.hostname or ""
    user = parsed.username or ""
    password = parsed.password or ""
    http_url = f"https://{host}/sql"
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return http_url, token

def _calculate_goal_met(current: int, tomorrow: int, multiplier: float, daily_done: int) -> bool:
    """Ported ReviewPump logic."""
    if current == 0 and tomorrow == 0:
        return True
        
    # Multiplier to days mapping
    clearance_days = {
        2: 14.0,
        3: 10.0,
        4: 7.0,
        5: 5.0,
        6: 3.0,
        7: 2.0,
        10: 1.0,
    }.get(int(multiplier))

    if clearance_days is None: # Maintenance mode
        target = tomorrow
    else:
        target = int(tomorrow + (current / clearance_days))

    if target > 0 or (current > 0 and multiplier > 1.0):
        return daily_done >= target
    else:
        return current == 0

async def _get_status(neon_url: str, user_id: str) -> dict:
    import httpx
    http_url, auth_token = _http_url_and_auth(neon_url)
    headers = {
        "Authorization": f"Basic {auth_token}",
        "Content-Type": "application/json",
    }
    
    goals = []
    
    # 1. Check Walk
    try:
        resp = httpx.post(http_url, headers=headers, json={"query": _WALK_SQL, "params": [user_id]}, timeout=5.0)
        resp.raise_for_status()
        rows = resp.json().get("rows", [])
        has_walked = int(rows[0].get("count", 0)) > 0 if rows else False
        goals.append({
            "name": "daily_walk",
            "label": "Daily Walk (2000 steps)",
            "satisfied": has_walked
        })
    except Exception as e:
        logger.error(f"Majesty Cake: Walk check failed: {e}")
        goals.append({"name": "daily_walk", "label": "Daily Walk (2000 steps)", "satisfied": False, "error": str(e)})

    # 2. Check Languages
    try:
        resp = httpx.post(http_url, headers=headers, json={"query": _LANG_SQL, "params": [user_id]}, timeout=5.0)
        resp.raise_for_status()
        rows = resp.json().get("rows", [])
        
        arabic_met = False
        greek_met = False
        
        for row in rows:
            name = row.get("language_name", "").upper()
            current = int(row.get("current_reviews", 0))
            tomorrow = int(row.get("tomorrow_reviews", 0))
            multiplier = float(row.get("pump_multiplier", 1.0))
            daily_done = int(row.get("daily_completions", 0))
            
            if name in ("ARABIC", "GREEK"):
                is_met = _calculate_goal_met(current, tomorrow, multiplier, daily_done)
                if name == "ARABIC": arabic_met = is_met
                if name == "GREEK": greek_met = is_met
                
        goals.append({"name": "arabic_review", "label": "Arabic Review Pump", "satisfied": arabic_met})
        goals.append({"name": "greek_review", "label": "Greek Review Pump", "satisfied": greek_met})
    except Exception as e:
        logger.error(f"Majesty Cake: Language check failed: {e}")
        goals.append({"name": "arabic_review", "label": "Arabic Review Pump", "satisfied": False, "error": str(e)})
        goals.append({"name": "greek_review", "label": "Greek Review Pump", "satisfied": False, "error": str(e)})

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
        }
    }

def _parse_query_params(path_with_query: str) -> dict:
    if not path_with_query or "?" not in path_with_query:
        return {}
    _, query = path_with_query.split("?", 1)
    parsed = parse_qs(query, keep_blank_values=False)
    return {k: v[0] for k, v in parsed.items() if v}

try:
    from spin_sdk.http import IncomingHandler as _SpinHandler, Request, Response
    from spin_sdk import variables as _spin_variables

    class IncomingHandler(_SpinHandler):
        def handle(self, request: Request) -> Response:
            try:
                params = _parse_query_params(request.uri)
                user_id = params.get("user_id", "").strip()
                if not user_id:
                    return Response(400, {"content-type": "application/json"}, json.dumps({"error": "user_id is required"}).encode())
                
                neon_url = _spin_variables.get("neon_db_url") or ""
                # Since we're in a sync handler context of spin_sdk, we might need a wrapper 
                # if _get_status is async. spin-python-sdk handle() can be async.
                import asyncio
                status = asyncio.run(_get_status(neon_url, user_id))
                
                return Response(200, {"content-type": "application/json"}, json.dumps(status).encode())
            except Exception as e:
                logger.error(f"majesty_cake HTTP handler error: {e}")
                return Response(500, {"content-type": "application/json"}, json.dumps({"error": "internal error"}).encode())

    def handle_request(request):
        return IncomingHandler().handle(request)

except ImportError:
    def handle_request(request):
        raise NotImplementedError("handle_request requires WASM runtime (spin_sdk)")
