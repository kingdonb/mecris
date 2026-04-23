"""
budget-governor-py WASM component — app.py (yebyen/mecris#262)

HTTP handler: POST /internal/budget-governor
Body JSON:
  {"action": "status"}
  {"action": "check",     "bucket": <str>, "cost": <float>}
  {"action": "record",    "bucket": <str>, "cost": <float>}
  {"action": "recommend"}
  {"action": "gate",      "bucket": <str>, "cost": <float>}

Returns JSON: action-specific response dict.

Phase 2 of the Python-native WASM migration (LOGIC_VACUUMING_CANDIDATES.md).
Ports the 5%/5% spend envelope logic from services/budget_governor.py with:
  - Spend log persistence via Spin KV (replaces file I/O)
  - Helix balance fetch via spin_sdk outbound HTTP (replaces requests)
  - Budget limits via Spin variables (replaces os.getenv)

Build:
    pip install -r requirements.txt && spin py2wasm app -o budget-governor-py.wasm

The pure-logic functions are self-contained and importable in tests without
the WASM runtime. The IncomingHandler class requires spin_sdk which is only
present inside the compiled WASM component — guarded by try/except ImportError.

Plan: yebyen/mecris#262
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mecris.budget_governor_component")

# ---------------------------------------------------------------------------
# Constants — 5%/5% envelope (matches services/budget_governor.py)
# ---------------------------------------------------------------------------

_DAYLIGHT_MINUTES = 780  # 13-hour daylight window
_ENVELOPE_WINDOW_MINUTES = int(_DAYLIGHT_MINUTES * 0.05)  # 39 min
_ENVELOPE_SPEND_RATIO = 0.05  # 5% of period quota per window

_KV_SPEND_LOG_KEY = "budget_spend_log"

# ---------------------------------------------------------------------------
# Default bucket configuration
# ---------------------------------------------------------------------------

BUCKET_TYPES: Dict[str, str] = {
    "helix": "spend",
    "gemini": "spend",
    "anthropic_api": "guard",
    "groq": "guard",
}

BUCKET_DESCRIPTIONS: Dict[str, str] = {
    "helix": "Helix SaaS credits (use-it-or-lose-it)",
    "gemini": "Gemini free-tier credits (use-it-or-lose-it)",
    "anthropic_api": "Anthropic paid API (ration carefully)",
    "groq": "Groq API (ration carefully)",
}

DEFAULT_LIMITS: Dict[str, float] = {
    "helix": 100.00,
    "gemini": 50.00,
    "anthropic_api": 20.89,
    "groq": 10.00,
}


def make_bucket_config(limits: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Build a bucket configuration dict from optional limit overrides."""
    effective = dict(DEFAULT_LIMITS)
    if limits:
        effective.update(limits)
    return {
        name: {
            "type": BUCKET_TYPES[name],
            "limit": effective[name],
            "description": BUCKET_DESCRIPTIONS[name],
        }
        for name in BUCKET_TYPES
    }


# ---------------------------------------------------------------------------
# Pure logic — no I/O, importable in tests without WASM runtime
# ---------------------------------------------------------------------------


def _calc_total_spent(spend_log: List[Dict[str, Any]], bucket_name: str) -> float:
    """Sum all spend events for a bucket across all time."""
    return sum(e["cost"] for e in spend_log if e["bucket"] == bucket_name)


def _calc_window_spent(
    spend_log: List[Dict[str, Any]],
    bucket_name: str,
    window_minutes: int = _ENVELOPE_WINDOW_MINUTES,
    _now: Optional[datetime] = None,
) -> float:
    """Sum spend events for a bucket in the last rolling window."""
    now = _now or datetime.utcnow()
    cutoff = now - timedelta(minutes=window_minutes)
    total = 0.0
    for e in spend_log:
        if e["bucket"] != bucket_name:
            continue
        ts = e["ts"]
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                continue
        if ts >= cutoff:
            total += e["cost"]
    return total


def check_envelope(
    spend_log: List[Dict[str, Any]],
    bucket_config: Dict[str, Any],
    bucket_name: str,
    cost_estimate: float,
    _now: Optional[datetime] = None,
) -> str:
    """
    Returns 'allow', 'defer', or 'deny' based on the 5%/5% rule.

    - 'deny'  : total spend already at or above the period limit.
    - 'defer' : within the rolling 39-min window, adding this cost would
                exceed 5% of the period quota.
    - 'allow' : safe to proceed.
    """
    if bucket_name not in bucket_config:
        raise ValueError(f"Unknown bucket: {bucket_name!r}")
    limit = bucket_config[bucket_name]["limit"]

    if _calc_total_spent(spend_log, bucket_name) >= limit:
        return "deny"

    window_cap = _ENVELOPE_SPEND_RATIO * limit
    if _calc_window_spent(spend_log, bucket_name, _now=_now) + cost_estimate > window_cap:
        return "defer"

    return "allow"


def recommend_bucket(
    spend_log: List[Dict[str, Any]],
    bucket_config: Dict[str, Any],
) -> str:
    """
    Returns the name of the best available bucket.

    Priority:
      1. SPEND buckets not exhausted (Helix Inversion — use them up).
      2. GUARD buckets not exhausted (fallback).
      3. Least-spent GUARD bucket (emergency fallback when all are tight).
    """
    spend_available = [
        name
        for name, cfg in bucket_config.items()
        if cfg["type"] == "spend"
        and _calc_total_spent(spend_log, name) < cfg["limit"]
    ]
    if spend_available:
        return max(
            spend_available,
            key=lambda n: bucket_config[n]["limit"] - _calc_total_spent(spend_log, n),
        )

    guard_available = [
        name
        for name, cfg in bucket_config.items()
        if cfg["type"] == "guard"
        and _calc_total_spent(spend_log, name) < cfg["limit"]
    ]
    if guard_available:
        return min(
            guard_available,
            key=lambda n: _calc_total_spent(spend_log, n) / bucket_config[n]["limit"],
        )

    return min(
        bucket_config.keys(),
        key=lambda n: _calc_total_spent(spend_log, n) / bucket_config[n]["limit"],
    )


def get_status(
    spend_log: List[Dict[str, Any]],
    bucket_config: Dict[str, Any],
    helix_live_balance: Optional[float] = None,
) -> Dict[str, Any]:
    """Return a full status dict matching the get_budget_status MCP tool shape."""
    bucket_report: Dict[str, Any] = {}
    all_denied = True

    for name, cfg in bucket_config.items():
        spent = _calc_total_spent(spend_log, name)
        window = _calc_window_spent(spend_log, name)
        limit = cfg["limit"]
        envelope = check_envelope(spend_log, bucket_config, name, 0.01)
        if envelope != "deny":
            all_denied = False

        bucket_report[name] = {
            "type": cfg["type"],
            "limit": limit,
            "spent_total": round(spent, 4),
            "spent_window_39min": round(window, 4),
            "remaining": round(max(0.0, limit - spent), 4),
            "envelope": envelope,
            "description": cfg.get("description", ""),
        }

    if helix_live_balance is not None:
        bucket_report["helix"]["live_balance"] = helix_live_balance

    return {
        "buckets": bucket_report,
        "recommendation": recommend_bucket(spend_log, bucket_config),
        "envelope_status": "HALTED" if all_denied else "OK",
        "window_minutes": _ENVELOPE_WINDOW_MINUTES,
        "envelope_spend_pct": int(_ENVELOPE_SPEND_RATIO * 100),
    }


def budget_gate(
    spend_log: List[Dict[str, Any]],
    bucket_config: Dict[str, Any],
    bucket: str,
    cost_estimate: float = 0.01,
) -> Optional[Dict[str, Any]]:
    """
    Enforcement guard for cost-incurring handlers.

    Returns None if the call should proceed, or a dict if blocked/warned.
    Only hard-blocks on 'deny'. 'defer' returns a warning (not a block).
    """
    result = check_envelope(spend_log, bucket_config, bucket, cost_estimate)
    recommendation = recommend_bucket(spend_log, bucket_config)

    if result == "deny":
        return {
            "budget_halted": True,
            "bucket": bucket,
            "envelope": result,
            "routing_recommendation": recommendation,
            "message": (
                f"Budget DENY for bucket '{bucket}': spend limit reached. "
                f"Try routing to: {recommendation}"
            ),
        }

    if result == "defer":
        return {
            "budget_halted": False,
            "warning": (
                f"Budget DEFER for bucket '{bucket}': rate envelope is full "
                f"(>5% of quota spent in last 39 min). "
                f"Consider routing to: {recommendation}"
            ),
            "bucket": bucket,
            "envelope": result,
            "routing_recommendation": recommendation,
        }

    return None


def _parse_request(body_bytes: bytes) -> Dict[str, Any]:
    """Parse JSON request body. Returns dict with defaults for missing fields."""
    try:
        data = json.loads(body_bytes or b"{}")
    except (json.JSONDecodeError, ValueError):
        data = {}
    return {
        "action": str(data.get("action", "status")),
        "bucket": str(data.get("bucket", "")),
        "cost": float(data.get("cost", 0.01)),
    }


def _json_ok(d: dict) -> bytes:
    """Serialize a dict to JSON bytes."""
    return json.dumps(d).encode()


def _error_json(message: str) -> bytes:
    """Serialize an error message to JSON bytes."""
    return json.dumps({"error": message}).encode()


def _load_spend_log_from_json(raw: Optional[bytes]) -> List[Dict[str, Any]]:
    """Parse spend log from JSON bytes. Returns empty list on any error."""
    if not raw:
        return []
    try:
        entries = json.loads(raw)
        return [
            {"bucket": e["bucket"], "cost": float(e["cost"]), "ts": e["ts"]}
            for e in entries
        ]
    except Exception:
        return []


def _dump_spend_log_to_json(spend_log: List[Dict[str, Any]]) -> bytes:
    """Serialize spend log to JSON bytes for KV storage."""
    serializable = []
    for e in spend_log:
        ts = e["ts"]
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        serializable.append({"bucket": e["bucket"], "cost": e["cost"], "ts": ts})
    return json.dumps(serializable).encode()


def make_spend_entry(bucket_name: str, cost: float) -> Dict[str, Any]:
    """Create a new spend log entry with the current UTC timestamp."""
    return {
        "bucket": bucket_name,
        "cost": cost,
        "ts": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# HTTP handler — operational inside the WASM runtime only.
# All pure logic above is importable in tests without the WASM runtime.
# ---------------------------------------------------------------------------
try:
    from spin_sdk.http import IncomingHandler as _SpinHandler, Request, Response
    from spin_sdk import variables
    import spin_sdk.key_value as kv

    def _get_bucket_config_from_spin_vars() -> Dict[str, Any]:
        """Load budget limits from Spin variables, falling back to defaults."""
        limits: Dict[str, float] = {}
        var_map = {
            "helix": "helix_credit_limit",
            "gemini": "gemini_free_limit",
            "anthropic_api": "anthropic_budget_limit",
            "groq": "groq_budget_limit",
        }
        for bucket, var_name in var_map.items():
            try:
                val = variables.get(var_name)
                if val:
                    limits[bucket] = float(val)
            except Exception:
                pass
        return make_bucket_config(limits)

    def _fetch_helix_balance_spin(base_url: str, api_key: str) -> Optional[float]:
        """Fetch live Helix balance via Spin outbound HTTP."""
        try:
            from spin_sdk.http import send as spin_send

            resp = spin_send(
                Request(
                    "GET",
                    f"{base_url.rstrip('/')}/api/v1/me",
                    {"Authorization": f"Bearer {api_key}"},
                    None,
                )
            )
            if resp.status == 200:
                data = json.loads(resp.body)
                balance = data.get("balance") or data.get("credit_balance")
                if balance is not None:
                    return float(balance)
        except Exception as exc:
            logger.debug("Helix balance fetch failed: %s", exc)
        return None

    class IncomingHandler(_SpinHandler):
        """Spin HTTP handler for POST /internal/budget-governor."""

        def handle(self, request: Request) -> Response:
            try:
                params = _parse_request(request.body)
                action = params["action"]

                store = kv.open_default()
                raw = store.get(_KV_SPEND_LOG_KEY)
                spend_log = _load_spend_log_from_json(raw)
                bucket_config = _get_bucket_config_from_spin_vars()

                if action == "status":
                    helix_live = None
                    try:
                        base_url = variables.get("anthropic_base_url") or ""
                        api_key = variables.get("anthropic_api_key") or ""
                        if base_url and api_key:
                            helix_live = _fetch_helix_balance_spin(base_url, api_key)
                    except Exception:
                        pass
                    result = get_status(spend_log, bucket_config, helix_live)
                    return Response(200, {"content-type": "application/json"}, _json_ok(result))

                elif action == "check":
                    bucket = params["bucket"]
                    cost = params["cost"]
                    if not bucket or bucket not in bucket_config:
                        return Response(
                            400,
                            {"content-type": "application/json"},
                            _error_json(f"unknown bucket: {bucket!r}"),
                        )
                    envelope = check_envelope(spend_log, bucket_config, bucket, cost)
                    return Response(
                        200,
                        {"content-type": "application/json"},
                        _json_ok({"envelope": envelope, "bucket": bucket}),
                    )

                elif action == "record":
                    bucket = params["bucket"]
                    cost = params["cost"]
                    if not bucket or bucket not in bucket_config:
                        return Response(
                            400,
                            {"content-type": "application/json"},
                            _error_json(f"unknown bucket: {bucket!r}"),
                        )
                    entry = make_spend_entry(bucket, cost)
                    spend_log.append(entry)
                    store.set(_KV_SPEND_LOG_KEY, _dump_spend_log_to_json(spend_log))
                    return Response(
                        200,
                        {"content-type": "application/json"},
                        _json_ok({"recorded": True, "bucket": bucket, "cost": cost}),
                    )

                elif action == "recommend":
                    recommendation = recommend_bucket(spend_log, bucket_config)
                    return Response(
                        200,
                        {"content-type": "application/json"},
                        _json_ok({"recommendation": recommendation}),
                    )

                elif action == "gate":
                    bucket = params["bucket"]
                    cost = params["cost"]
                    if not bucket or bucket not in bucket_config:
                        return Response(
                            400,
                            {"content-type": "application/json"},
                            _error_json(f"unknown bucket: {bucket!r}"),
                        )
                    gate_result = budget_gate(spend_log, bucket_config, bucket, cost)
                    if gate_result is None:
                        return Response(
                            200,
                            {"content-type": "application/json"},
                            _json_ok({"allowed": True}),
                        )
                    return Response(
                        200,
                        {"content-type": "application/json"},
                        _json_ok(gate_result),
                    )

                else:
                    return Response(
                        400,
                        {"content-type": "application/json"},
                        _error_json(f"unknown action: {action!r}"),
                    )

            except Exception as exc:
                logger.error(f"budget_governor_py component error: {exc}")
                return Response(
                    500,
                    {"content-type": "application/json"},
                    _error_json("internal error"),
                )

    def handle_request(request):
        """Top-level entry point for spin py2wasm."""
        return IncomingHandler().handle(request)

except ImportError:
    # Fail gracefully outside WASM runtime
    def handle_request(request):
        raise NotImplementedError("handle_request requires WASM runtime (spin_sdk)")
