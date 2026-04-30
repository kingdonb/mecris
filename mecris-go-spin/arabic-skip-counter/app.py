"""
arabic-skip-counter WASM component — app.py (Phase 1.6 / kingdonb/mecris#157)

HTTP trigger: GET /internal/arabic-skip-count?user_id=<id>&hours=<n>
Returns JSON: {"skip_count": <u32>}
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
from urllib.parse import urlparse, parse_qs

import httpx

try:
    from spin_sdk import http, variables as _spin_variables
    from spin_sdk.http import Request, Response
    _SPIN_AVAILABLE = True
except ImportError:
    _SPIN_AVAILABLE = False
    class _FakeHttp:
        class Handler:
            pass
    http = _FakeHttp()  # type: ignore[assignment]
    class Request:  # type: ignore[no-redef]
        pass
    class Response:  # type: ignore[no-redef]
        pass

# Setup logging
logger = logging.getLogger("mecris.arabic_skip_counter")


def _parse_query_params(uri: Optional[str]) -> Dict[str, str]:
    if not uri:
        return {}
    parsed = urlparse(uri)
    return {k: v[0] for k, v in parse_qs(parsed.query).items()}


def _neon_http_url(postgres_url: str) -> str:
    """Convert postgres://user:pass@host/db → https://host/sql"""
    parsed = urlparse(postgres_url)
    return f"https://{parsed.hostname}/sql"


def _count_reminders(neon_url: str, user_id: str, hours: int) -> int:
    """Query Neon HTTP SQL API and return the skip count. Returns 0 on any error."""
    if not neon_url:
        return 0
    try:
        http_url = _neon_http_url(neon_url)
        parsed = urlparse(neon_url)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        sql = (
            "SELECT COUNT(*) as count FROM message_log "
            "WHERE type IN ($1, $2) AND user_id = $3 AND created_at >= $4"
        )
        resp = httpx.post(
            http_url,
            json={"query": sql, "params": ["arabic_skip", "SKIP", user_id, cutoff]},
            auth=(parsed.username, parsed.password) if parsed.username else None,
        )
        resp.raise_for_status()
        rows = resp.json().get("rows", [])
        if not rows:
            return 0
        return int(rows[0].get("count", 0))
    except Exception as e:
        print(f"Database error in arabic_skip_counter: {e}")
        return 0

def _json_response(count: int) -> bytes:
    return json.dumps({"skip_count": count}).encode()

def _error_json(message: str) -> bytes:
    return json.dumps({"error": message}).encode()

class HttpHandler(http.Handler):
    async def handle_request(self, request: Request) -> Response:
        try:
            params = _parse_query_params(request.uri)
            user_id = params.get("user_id", "").strip()
            if not user_id:
                return Response(
                    400,
                    {"content-type": "application/json"},
                    _error_json("user_id is required"),
                )
            hours_str = params.get("hours", "24")
            try:
                hours = int(hours_str)
                if hours <= 0:
                    raise ValueError("hours must be positive")
            except ValueError:
                return Response(
                    400,
                    {"content-type": "application/json"},
                    _error_json(f"invalid hours value: {hours_str!r}"),
                )
            
            neon_url = (await _spin_variables.get("neon_db_url")) or ""
            count = _count_reminders(neon_url, user_id, hours)
            return Response(
                200,
                {"content-type": "application/json"},
                _json_response(count),
            )
        except Exception as e:
            print(f"arabic_skip_counter HTTP handler error: {e}")
            return Response(
                500,
                {"content-type": "application/json"},
                _error_json("internal error"),
            )

# Mandatory export for spin-sdk v4
if _SPIN_AVAILABLE:
    incoming_handler = HttpHandler()
