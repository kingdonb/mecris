"""
log-message-py WASM component — app.py (yebyen/mecris#267)

HTTP handler: POST /internal/log-message
Body JSON:
  {"type": <str>, "channel": <str>, "sent_at": <ISO 8601 string, optional>}

  type:    notification category — e.g. "walk_reminder", "arabic_pressure"
  channel: delivery channel — e.g. "android_native"
  sent_at: client-side send timestamp (ISO 8601); defaults to server time if omitted

Returns JSON:
  {"logged": true, "entry_count": <int>, "logged_at": <ISO 8601>}
  or
  {"error": <str>}  (HTTP 400/500)

Also handles GET /internal/log-message:
  Returns JSON: {"entries": [...], "entry_count": <int>}

Part of the Observability Mandate (kingdonb/mecris#245, kingdonb/mecris#213).
Follows the componentize-py / Spin KV pattern established in budget-governor-py.

Build:
    uv run componentize-py -w spin:up/http-trigger@4.0.0 componentize app -o log-message-py.wasm

Plan: yebyen/mecris#267
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from spin_sdk import http
    from spin_sdk.http import Request, Response
    import spin_sdk.key_value as kv
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

logger = logging.getLogger("mecris.log_message_component")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_KV_MESSAGE_LOG_KEY = "message_log"
_MAX_LOG_ENTRIES = 1000  # rolling cap to avoid unbounded KV growth

VALID_TYPES = {
    "walk_reminder",
    "arabic_pressure",
    "sovereign_fallback",
    "greek_nag",
    "generic",
}

VALID_CHANNELS = {
    "android_native",
    "sms",
    "whatsapp",
    "mcp",
    "internal",
}


# ---------------------------------------------------------------------------
# Pure logic — no I/O, importable in tests without WASM runtime
# ---------------------------------------------------------------------------


def validate_entry(data: Dict[str, Any]) -> Optional[str]:
    """
    Validate a log entry dict. Returns an error string or None if valid.
    Unknown types/channels are accepted (open schema) — only missing required
    fields are rejected.
    """
    if not data.get("type"):
        return "missing required field: type"
    if not data.get("channel"):
        return "missing required field: channel"
    return None


def make_log_entry(
    entry_type: str,
    channel: str,
    sent_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a normalized message log entry."""
    logged_at = datetime.now(timezone.utc).isoformat()
    return {
        "type": entry_type,
        "channel": channel,
        "sent_at": sent_at or logged_at,
        "logged_at": logged_at,
    }


def append_entry(
    log: List[Dict[str, Any]],
    entry: Dict[str, Any],
    max_entries: int = _MAX_LOG_ENTRIES,
) -> List[Dict[str, Any]]:
    """
    Append entry to log and enforce rolling cap.
    Returns the updated log (oldest entries pruned if over max_entries).
    """
    log = log + [entry]
    if len(log) > max_entries:
        log = log[-max_entries:]
    return log


def _parse_request(body_bytes: Optional[bytes]) -> Dict[str, Any]:
    """Parse JSON request body. Returns dict with empty strings for missing fields."""
    try:
        data = json.loads(body_bytes or b"{}")
    except (json.JSONDecodeError, ValueError):
        data = {}
    return {
        "type": str(data.get("type", "")),
        "channel": str(data.get("channel", "")),
        "sent_at": str(data.get("sent_at", "")) or None,
    }


def _json_ok(d: dict) -> bytes:
    """Serialize a dict to JSON bytes."""
    return json.dumps(d).encode()


def _error_json(message: str) -> bytes:
    """Serialize an error message to JSON bytes."""
    return json.dumps({"error": message}).encode()


def _load_log_from_json(raw: Optional[bytes]) -> List[Dict[str, Any]]:
    """Parse message log from JSON bytes. Returns empty list on any error."""
    if not raw:
        return []
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list):
            return []
        return [
            {
                "type": str(e.get("type", "")),
                "channel": str(e.get("channel", "")),
                "sent_at": str(e.get("sent_at", "")),
                "logged_at": str(e.get("logged_at", "")),
            }
            for e in entries
        ]
    except Exception:
        return []


def _dump_log_to_json(log: List[Dict[str, Any]]) -> bytes:
    """Serialize message log to JSON bytes for KV storage."""
    return json.dumps(log).encode()


# ---------------------------------------------------------------------------
# HTTP handler — operational inside the WASM runtime only.
# ---------------------------------------------------------------------------

class HttpHandler(http.Handler):
    async def handle_request(self, request: Request) -> Response:
        try:
            with (await kv.open_default()) as store:
                raw = await store.get(_KV_MESSAGE_LOG_KEY)
                log = _load_log_from_json(raw)

                method = getattr(request, "method", "POST").upper()

                if method == "GET":
                    return Response(
                        200,
                        {"content-type": "application/json"},
                        _json_ok({"entries": log, "entry_count": len(log)}),
                    )

                # POST — log a new notification
                params = _parse_request(request.body)
                error = validate_entry(params)
                if error:
                    return Response(
                        400,
                        {"content-type": "application/json"},
                        _error_json(error),
                    )

                entry = make_log_entry(params["type"], params["channel"], params["sent_at"])
                log = append_entry(log, entry)
                await store.set(_KV_MESSAGE_LOG_KEY, _dump_log_to_json(log))

                return Response(
                    200,
                    {"content-type": "application/json"},
                    _json_ok({
                        "logged": True,
                        "entry_count": len(log),
                        "logged_at": entry["logged_at"],
                    }),
                )

        except Exception as exc:
            print(f"log_message_py component error: {exc}")
            return Response(
                500,
                {"content-type": "application/json"},
                _error_json("internal error"),
            )

# Mandatory export for spin-sdk v4
if _SPIN_AVAILABLE:
    incoming_handler = HttpHandler()
