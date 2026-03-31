"""
arabic-skip-counter WASM component — app.py (Phase 1.6: HTTP trigger)

HTTP handler: GET /internal/arabic-skip-count?user_id=<id>&hours=<n>
Reads neon_db_url from Spin variables.
Returns JSON: {"skip_count": <u32>}

Implementation: componentize-py + spin_sdk HTTP incoming-handler.

Build:
    pip install -r requirements.txt && spin py2wasm app -o arabic-skip-counter.wasm

The helper functions (_count_reminders, _parse_query_params, etc.) are
self-contained and importable in tests without the WASM runtime.
The IncomingHandler class requires spin_sdk which is only present inside
the compiled WASM component — it is guarded by try/except ImportError.

Note: the logic mirrors services/arabic_skip_counter.py exactly.
Keeping it self-contained avoids a dependency on the repo layout at
component-build time.
"""

import base64
import json
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("mecris.arabic_skip_counter_component")

_ARABIC_REMINDER_TYPES = ("arabic_review_reminder", "arabic_review_escalation")

_SQL = (
    "SELECT COUNT(*) FROM message_log"
    " WHERE (type = $1 OR type = $2) AND user_id = $3 AND sent_at >= $4"
)


def _http_url_and_auth(neon_url: str) -> tuple:
    """Derive Neon HTTP endpoint URL and Basic auth token from a postgres:// URL."""
    parsed = urlparse(neon_url)
    host = parsed.hostname or ""
    user = parsed.username or ""
    password = parsed.password or ""
    http_url = f"https://{host}/sql"
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return http_url, token


def _count_reminders(neon_url: str, user_id: str, hours: int) -> int:
    """Count Arabic reminder messages in the last `hours` hours via Neon HTTP API."""
    import httpx  # lazy import: bundled by componentize-py, not available in all hosts

    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    try:
        http_url, auth_token = _http_url_and_auth(neon_url)
        response = httpx.post(
            http_url,
            headers={
                "Authorization": f"Basic {auth_token}",
                "Content-Type": "application/json",
            },
            json={
                "query": _SQL,
                "params": [
                    _ARABIC_REMINDER_TYPES[0],
                    _ARABIC_REMINDER_TYPES[1],
                    user_id,
                    cutoff,
                ],
            },
            timeout=5.0,
        )
        response.raise_for_status()
        data = response.json()
        rows = data.get("rows", [])
        return int(rows[0].get("count", 0)) if rows else 0
    except Exception as e:
        logger.error(f"arabic_skip_counter component: HTTP query failed: {e}")
        return 0


def _parse_query_params(path_with_query: str) -> dict:
    """Extract query parameters from a URL path+query string.

    Returns a flat dict of {key: first_value}.
    Returns {} if there is no query string or path_with_query is empty/None.

    Examples:
        "/internal/arabic-skip-count?user_id=yebyen&hours=24"
        -> {"user_id": "yebyen", "hours": "24"}

        "/internal/arabic-skip-count"
        -> {}
    """
    if not path_with_query or "?" not in path_with_query:
        return {}
    _, query = path_with_query.split("?", 1)
    parsed = parse_qs(query, keep_blank_values=False)
    return {k: v[0] for k, v in parsed.items() if v}


def _json_response(count: int) -> bytes:
    """Serialize skip count to JSON bytes: {"skip_count": <n>}."""
    return json.dumps({"skip_count": count}).encode()


def _error_json(message: str) -> bytes:
    """Serialize an error message to JSON bytes: {"error": <message>}."""
    return json.dumps({"error": message}).encode()


# ---------------------------------------------------------------------------
# HTTP handler — operational inside the WASM runtime only.
# spin_sdk is provided by componentize-py at build time (from requirements.txt).
# Outside the WASM runtime (e.g. in pytest), the import fails gracefully and
# helper functions above are still importable and testable.
# ---------------------------------------------------------------------------
try:
    from spin_sdk.http import IncomingHandler as _SpinHandler, Request, Response
    from spin_sdk import variables as _spin_variables

    class IncomingHandler(_SpinHandler):
        """Spin HTTP handler for GET /internal/arabic-skip-count."""

        def handle(self, request: Request) -> Response:
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
                neon_url = _spin_variables.get("neon_db_url") or ""
                count = _count_reminders(neon_url, user_id, hours)
                return Response(
                    200,
                    {"content-type": "application/json"},
                    _json_response(count),
                )
            except Exception as e:
                logger.error(f"arabic_skip_counter HTTP handler error: {e}")
                return Response(
                    500,
                    {"content-type": "application/json"},
                    _error_json("internal error"),
                )

except ImportError:
    # Not inside the WASM runtime — IncomingHandler is unavailable.
    # Tests import this module directly and call the helper functions above.
    pass
