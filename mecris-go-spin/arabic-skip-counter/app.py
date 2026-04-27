"""
arabic-skip-counter WASM component — app.py (Phase 1.6 / kingdonb/mecris#157)

HTTP trigger: GET /internal/arabic-skip-count?user_id=<id>&hours=<n>
Returns JSON: {"skip_count": <u32>}
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from urllib.parse import urlparse, parse_qs

try:
    from spin_sdk import http, variables as _spin_variables, postgres
    from spin_sdk.http import Request, Response
    from spin_sdk.wit.imports.spin_postgres_postgres_4_2_0 import (
        ParameterValue_Str,
        DbValue_Int64,
        DbValue_Int32
    )
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
    class ParameterValue_Str:  # type: ignore[no-redef]
        def __init__(self, value=None): self.value = value
    class DbValue_Int64:  # type: ignore[no-redef]
        def __init__(self, value=0): self.value = value
    class DbValue_Int32:  # type: ignore[no-redef]
        def __init__(self, value=0): self.value = value

# Setup logging
logger = logging.getLogger("mecris.arabic_skip_counter")

def _parse_query_params(uri: str) -> Dict[str, str]:
    parsed = urlparse(uri)
    return {k: v[0] for k, v in parse_qs(parsed.query).items()}

async def _count_reminders(neon_url: str, user_id: str, hours: int) -> int:
    if not neon_url:
        return 0

    try:
        conn = await postgres.Connection.open(neon_url)
        # Count entries in message_log that are "SKIP" within the last N hours
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        sql = "SELECT COUNT(*) FROM message_log WHERE user_id = $1 AND status = 'SKIP' AND created_at >= $2"
        params = [
            ParameterValue_Str(value=user_id),
            ParameterValue_Str(value=cutoff)
        ]
        
        columns, stream, future = await conn.query(sql, params)
        count = 0
        async for row in stream:
            # row is List[DbValue]
            val = row[0]
            if isinstance(val, DbValue_Int64):
                count = val.value
            elif isinstance(val, DbValue_Int32):
                count = val.value
            break # Expecting only one row
            
        return int(count)
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
            count = await _count_reminders(neon_url, user_id, hours)
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
