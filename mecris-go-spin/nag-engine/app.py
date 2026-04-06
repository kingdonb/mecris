"""
Nag Engine WASM component — app.py (Unified Behavioral Escalation)

HTTP handler: POST /internal/nag-check?user_id=<id>
Reads neon_db_url from Spin variables.
Returns JSON with reminder decision and message.

Features:
1. Nag Ladder (SYS-002): 3-tier escalation (Gentle, Escalated, High Urgency).
2. Rate Limiting: 2x/hour global cap.
3. Cooldowns: Per-type cooldown with dynamic evening reduction (fuzz).
4. Sleep Windows: Normal (8pm-8am) and Emergency (12am-8am).
5. Boris & Fiona: Walk reminders with weather-aware messaging.

Implementation: componentize-py + spin_sdk HTTP incoming-handler.
"""

import base64
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
import zoneinfo
from dateutil.parser import parse

logger = logging.getLogger("mecris.nag_engine_component")

# US/Eastern is the canonical timezone for Mecris day boundaries
EASTERN = zoneinfo.ZoneInfo("America/New_York")

TIER2_IDLE_HOURS = 6.0

_SQL_LAST_SENT = (
    "SELECT sent_at FROM message_log "
    "WHERE user_id = $1 AND (type = $2 OR $2 IS NULL) "
    "ORDER BY sent_at DESC LIMIT 1"
)

_SQL_ALERTS = (
    "SELECT slug, title, runway, derail_risk FROM beeminder_alerts "
    "WHERE user_id = $1"
)

_SQL_LANGS = (
    "SELECT language_name, current_reviews, tomorrow_reviews, pump_multiplier::FLOAT8, daily_completions "
    "FROM language_stats WHERE user_id = $1"
)

_SQL_WALK = (
    "SELECT COUNT(*) FROM walk_inferences "
    "WHERE user_id = $1 AND (start_time::TIMESTAMPTZ AT TIME ZONE 'US/Eastern')::DATE = (CURRENT_TIMESTAMP AT TIME ZONE 'US/Eastern')::DATE "
    "AND CAST(step_count AS INTEGER) >= 2000"
)

def _http_url_and_auth(neon_url: str) -> tuple:
    parsed = urlparse(neon_url)
    host = parsed.hostname or ""
    user = parsed.username or ""
    password = parsed.password or ""
    http_url = f"https://{host}/sql"
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return http_url, token

class NagEngine:
    def __init__(self, neon_url: str, user_id: str):
        self.neon_url = neon_url
        self.user_id = user_id
        self.http_url, self.auth_token = _http_url_and_auth(neon_url)
        self.headers = {"Authorization": f"Basic {self.auth_token}", "Content-Type": "application/json"}

    async def _query(self, sql: str, params: list) -> list:
        import httpx
        resp = httpx.post(self.http_url, headers=self.headers, json={"query": sql, "params": params}, timeout=5.0)
        resp.raise_for_status()
        return resp.json().get("rows", [])

    async def _get_hours_since_last(self, msg_type: str = None) -> float:
        rows = await self._query(_SQL_LAST_SENT, [self.user_id, msg_type])
        if not rows:
            return 999.0
        last_sent = parse(rows[0]["sent_at"])
        now = datetime.now(timezone.utc)
        return (now - last_sent).total_seconds() / 3600.0

    def _parse_runway_hours(self, runway: str) -> float:
        try:
            parts = runway.lower().split()
            if len(parts) >= 2 and "hour" in parts[1]:
                return float(parts[0])
        except (ValueError, IndexError):
            pass
        return 999.0

    def _calculate_dynamic_cooldown(self, base_cooldown: float, current_hour: int) -> float:
        reduction = 0.0
        if current_hour >= 16:
            reduction = (current_hour - 16) * 0.15
        fuzz = random.uniform(-0.25, 0.25)
        return max(0.75, base_cooldown - reduction + fuzz)

    async def check_reminders(self) -> dict:
        # 1. Global Rate Limit (30m)
        hours_since_any = await self._get_hours_since_last(None)
        if hours_since_any < 0.5:
            return {"should_send": False, "reason": f"Global rate limit (last sent {hours_since_any*60:.1f}m ago)"}

        # 2. Fetch Context Data
        alerts = await self._query(_SQL_ALERTS, [self.user_id])
        langs = await self._query(_SQL_LANGS, [self.user_id])
        walk_rows = await self._query(_SQL_WALK, [self.user_id])
        has_walked = int(walk_rows[0]["count"]) > 0 if walk_rows else False

        now_eastern = datetime.now(EASTERN)
        hour = now_eastern.hour
        
        # 3. Tier 3: Critical Runway (< 2h)
        subhour_critical = [g for g in alerts if self._parse_runway_hours(g.get("runway", "")) < 2.0]
        if subhour_critical:
            hours_since_urgent = await self._get_hours_since_last("beeminder_emergency_tier3")
            if hours_since_urgent >= 1.0:
                target = subhour_critical[0]
                return {
                    "should_send": True, "type": "beeminder_emergency_tier3", "tier": 3,
                    "message": f"🚨🚨🚨 CRITICAL EMERGENCY: {target.get('title')} derails in under 2 hours — TAKE ACTION NOW."
                }

        # 4. Emergency Sleep Window (12am-8am)
        if hour < 8:
            return {"should_send": False, "reason": "Emergency sleep window active (12am-8am)"}

        # 5. Language Emergencies (Tier 1/2)
        arabic_alert = next((g for g in alerts if g.get("slug") == "reviewstack" and g.get("derail_risk") == "CRITICAL"), None)
        if arabic_alert:
            dynamic_cooldown = self._calculate_dynamic_cooldown(2.0, hour)
            hours_since_arabic = await self._get_hours_since_last("arabic_review_reminder")
            if hours_since_arabic >= dynamic_cooldown:
                # Promotion to Tier 2
                if hours_since_arabic >= TIER2_IDLE_HOURS:
                    return {
                        "should_send": True, "type": "arabic_review_reminder", "tier": 2,
                        "message": f"🚨 ESCALATED: Arabic reviews still overdue after {hours_since_arabic:.0f}h. reviewstack won't fix itself — open Clozemaster NOW. 📚"
                    }
                return {
                    "should_send": True, "type": "arabic_review_reminder", "tier": 1,
                    "message": f"🚨 Arabic reviews are CRITICAL — you have {arabic_alert.get('runway')} remaining. Open Clozemaster NOW!"
                }

        # 6. Normal Sleep Window (8pm-8am)
        if hour >= 20:
            return {"should_send": False, "reason": "Normal sleep window active (8pm-8am)"}

        # 7. Walk Reminders (2pm-6pm)
        if 14 <= hour <= 18 and not has_walked:
            hours_since_walk = await self._get_hours_since_last("walk_reminder")
            if hours_since_walk >= 2.5:
                if hours_since_walk >= TIER2_IDLE_HOURS:
                    return {
                        "should_send": True, "type": "walk_reminder", "tier": 2,
                        "message": f"⚠️ Still no walk after {hours_since_walk:.0f}h. Boris and Fiona are not impressed. Get outside NOW. 🐕🚨"
                    }
                return {
                    "should_send": True, "type": "walk_reminder", "tier": 1,
                    "message": "🐕 Afternoon walk time! Boris and Fiona are ready for their adventure. 🌅"
                }

        return {"should_send": False, "reason": "No conditions met for reminder"}

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
                engine = NagEngine(neon_url, user_id)
                
                import asyncio
                result = asyncio.run(engine.check_reminders())
                
                return Response(200, {"content-type": "application/json"}, json.dumps(result).encode())
            except Exception as e:
                logger.error(f"nag_engine HTTP handler error: {e}")
                return Response(500, {"content-type": "application/json"}, json.dumps({"error": "internal error", "details": str(e)}).encode())

    def handle_request(request):
        return IncomingHandler().handle(request)

except ImportError:
    def handle_request(request):
        raise NotImplementedError("handle_request requires WASM runtime (spin_sdk)")
