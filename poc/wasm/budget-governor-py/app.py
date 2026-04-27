"""
budget-governor-py: Python-native WASM component (componentize-py + spin_sdk, Phase 1.7.2 / kingdonb/mecris#214).

Ports the spend envelope logic (5%/5% soft-cap/hard-cap) from services/budget_governor.py to a WASM component.
Uses Spin Key-Value for spend log persistence and Spin Variables for limits.

HTTP trigger: POST /internal/budget-governor
Body JSON: {
  "action": "status" | "check" | "record" | "recommend" | "gate",
  "bucket": <string>,
  "cost": <float>
}
Returns JSON: Action-specific response dict
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

try:
    from spin_sdk import http, variables
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

logger = logging.getLogger("mecris.budget_governor_component")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_KV_SPEND_LOG_KEY = "budget_spend_log"
_WINDOW_MINUTES = 39
_ENVELOPE_SPEND_PCT = 5

_DEFAULT_LIMITS: Dict[str, Dict[str, Any]] = {
    "helix":         {"limit": 100.00, "type": "spend"},
    "gemini":        {"limit":  50.00, "type": "spend"},
    "anthropic_api": {"limit":  20.89, "type": "guard"},
    "groq":          {"limit":  10.00, "type": "guard"},
}

# ---------------------------------------------------------------------------
# Pure Logic & Data Models
# ---------------------------------------------------------------------------

def make_bucket_config(limits: Optional[Dict[str, float]] = None) -> Dict[str, Dict[str, Any]]:
    """Return bucket config dict with defaults. limits overrides specific bucket limits."""
    config: Dict[str, Dict[str, Any]] = {}
    for name, defaults in _DEFAULT_LIMITS.items():
        entry: Dict[str, Any] = {"limit": defaults["limit"], "type": defaults["type"]}
        if limits and name in limits:
            entry["limit"] = limits[name]
        config[name] = entry
    return config


def _calc_total_spent(log: List[Dict[str, Any]], bucket: str) -> float:
    """Sum all-time spend for a bucket, regardless of time window."""
    return sum(e["cost"] for e in log if e["bucket"] == bucket)


def _calc_window_spent(log: List[Dict[str, Any]], bucket: str) -> float:
    """Sum spend for a bucket within the rolling 39-minute window."""
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=_WINDOW_MINUTES)
    total = 0.0
    for entry in log:
        if entry["bucket"] != bucket:
            continue
        ts = entry["ts"]
        if not isinstance(ts, datetime):
            try:
                ts = datetime.fromisoformat(str(ts))
            except (ValueError, TypeError):
                continue  # skip unparseable timestamps
        if ts >= cutoff:
            total += entry["cost"]
    return total


def check_envelope(
    log: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    bucket: str,
    cost: float,
) -> str:
    """Return 'allow', 'defer', or 'deny'."""
    if bucket not in cfg:
        raise ValueError(f"Unknown bucket: {bucket!r}")
    limit = cfg[bucket]["limit"]
    total = _calc_total_spent(log, bucket)
    if total >= limit:
        return "deny"
    window_cap = limit * (_ENVELOPE_SPEND_PCT / 100.0)
    window = _calc_window_spent(log, bucket)
    if (window + cost) > window_cap:
        return "defer"
    return "allow"


def recommend_bucket(
    log: List[Dict[str, Any]],
    cfg: Dict[str, Any],
) -> str:
    """Return the best bucket — prefer 'spend' type, then least-used guard."""
    def _ratio(name: str) -> float:
        limit = cfg[name]["limit"]
        if limit <= 0:
            return float("inf")
        return _calc_total_spent(log, name) / limit

    spend_buckets = [n for n, c in cfg.items() if c["type"] == "spend"]
    guard_buckets = [n for n, c in cfg.items() if c["type"] == "guard"]

    available_spend = [n for n in spend_buckets if _calc_total_spent(log, n) < cfg[n]["limit"]]
    if available_spend:
        return min(available_spend, key=_ratio)

    if guard_buckets:
        return min(guard_buckets, key=_ratio)

    return min(cfg.keys(), key=_ratio)


def get_status(
    log: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    helix_live_balance: Optional[float] = None,
) -> Dict[str, Any]:
    """Return full status report."""
    buckets: Dict[str, Any] = {}
    for name in cfg:
        limit = cfg[name]["limit"]
        spent = _calc_total_spent(log, name)
        remaining = max(0.0, limit - spent)
        envelope = check_envelope(log, cfg, name, 0.0)
        entry: Dict[str, Any] = {
            "envelope": envelope,
            "spent_total": spent,
            "remaining": remaining,
        }
        if name == "helix" and helix_live_balance is not None:
            entry["live_balance"] = helix_live_balance
        buckets[name] = entry

    all_denied = all(b["envelope"] == "deny" for b in buckets.values())
    return {
        "buckets": buckets,
        "envelope_status": "HALTED" if all_denied else "OK",
        "window_minutes": _WINDOW_MINUTES,
        "envelope_spend_pct": _ENVELOPE_SPEND_PCT,
        "recommendation": recommend_bucket(log, cfg),
    }


def budget_gate(
    log: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    bucket: str,
    cost: float = 0.01,
) -> Optional[Dict[str, Any]]:
    """Return None if allowed; dict with halted/deferred info otherwise."""
    envelope = check_envelope(log, cfg, bucket, cost)
    if envelope == "allow":
        return None
    routing = recommend_bucket(log, cfg)
    if envelope == "deny":
        return {
            "budget_halted": True,
            "envelope": "deny",
            "message": f"Budget limit reached for {bucket}. Try {routing}.",
            "routing_recommendation": routing,
        }
    # defer
    return {
        "budget_halted": False,
        "envelope": "defer",
        "warning": f"Window rate cap for {bucket} would be exceeded.",
        "routing_recommendation": routing,
    }


# ---------------------------------------------------------------------------
# WASM Infrastructure Helpers
# ---------------------------------------------------------------------------

class _DatetimeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def _load_spend_log_from_json(raw_bytes: Optional[bytes]) -> List[Dict[str, Any]]:
    if not raw_bytes:
        return []
    try:
        return json.loads(raw_bytes)
    except Exception:
        return []


def _dump_spend_log_to_json(spend_log: List[Dict[str, Any]]) -> bytes:
    serializable = spend_log[-200:]  # Keep last 200 entries to prevent KV bloat
    return json.dumps(serializable, cls=_DatetimeEncoder).encode()


def _parse_request(body_bytes: Optional[bytes]) -> Dict[str, Any]:
    try:
        data = json.loads(body_bytes or b"{}")
    except Exception:
        data = {}
    return {
        "action": str(data.get("action", "status")),
        "bucket": str(data.get("bucket", "")),
        "cost": float(data.get("cost", 0.01)),
    }


def _json_ok(data: Dict[str, Any]) -> bytes:
    return json.dumps(data).encode()


def _error_json(message: str) -> bytes:
    return json.dumps({"error": message}).encode()


def make_spend_entry(bucket_name: str, cost: float) -> Dict[str, Any]:
    return {
        "bucket": bucket_name,
        "cost": cost,
        "ts": datetime.utcnow().isoformat(),
    }


async def _get_bucket_config_from_spin_vars() -> Dict[str, Any]:
    limits: Dict[str, float] = {}
    var_map = {
        "helix": "helix_credit_limit",
        "gemini": "gemini_free_limit",
        "anthropic_api": "anthropic_budget_limit",
        "groq": "groq_budget_limit",
    }
    for bucket, var_name in var_map.items():
        try:
            val = await variables.get(var_name)
            if val:
                limits[bucket] = float(val)
        except Exception:
            pass
    return make_bucket_config(limits if limits else None)


async def _fetch_helix_balance_spin(base_url: str, api_key: str) -> Optional[float]:
    try:
        from spin_sdk.http import send as spin_send
        resp = await spin_send(
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
        print(f"Helix balance fetch failed: {exc}")
    return None


class HttpHandler(http.Handler):
    async def handle_request(self, request: Request) -> Response:
        try:
            params = _parse_request(request.body)
            action = params["action"]

            with (await kv.open_default()) as store:
                raw = await store.get(_KV_SPEND_LOG_KEY)
                spend_log = _load_spend_log_from_json(raw)
                bucket_config = await _get_bucket_config_from_spin_vars()

                if action == "status":
                    helix_live = None
                    try:
                        base_url = (await variables.get("anthropic_base_url")) or ""
                        api_key = (await variables.get("anthropic_api_key")) or ""
                        if base_url and api_key:
                            helix_live = await _fetch_helix_balance_spin(base_url, api_key)
                    except Exception:
                        pass
                    result = get_status(spend_log, bucket_config, helix_live)
                    return Response(200, {"content-type": "application/json"}, _json_ok(result))

                elif action == "check":
                    bucket = params["bucket"]
                    cost = params["cost"]
                    if not bucket or bucket not in bucket_config:
                        return Response(400, {"content-type": "application/json"}, _error_json(f"unknown bucket: {bucket!r}"))
                    envelope = check_envelope(spend_log, bucket_config, bucket, cost)
                    return Response(200, {"content-type": "application/json"}, _json_ok({"envelope": envelope, "bucket": bucket}))

                elif action == "record":
                    bucket = params["bucket"]
                    cost = params["cost"]
                    if not bucket or bucket not in bucket_config:
                        return Response(400, {"content-type": "application/json"}, _error_json(f"unknown bucket: {bucket!r}"))
                    entry = make_spend_entry(bucket, cost)
                    spend_log.append(entry)
                    await store.set(_KV_SPEND_LOG_KEY, _dump_spend_log_to_json(spend_log))
                    return Response(200, {"content-type": "application/json"}, _json_ok({"recorded": True, "bucket": bucket, "cost": cost}))

                elif action == "recommend":
                    recommendation = recommend_bucket(spend_log, bucket_config)
                    return Response(200, {"content-type": "application/json"}, _json_ok({"recommendation": recommendation}))

                elif action == "gate":
                    bucket = params["bucket"]
                    cost = params["cost"]
                    if not bucket or bucket not in bucket_config:
                        return Response(400, {"content-type": "application/json"}, _error_json(f"unknown bucket: {bucket!r}"))
                    gate_result = budget_gate(spend_log, bucket_config, bucket, cost)
                    if gate_result is None:
                        return Response(200, {"content-type": "application/json"}, _json_ok({"allowed": True}))
                    return Response(200, {"content-type": "application/json"}, _json_ok(gate_result))

                else:
                    return Response(400, {"content-type": "application/json"}, _error_json(f"unknown action: {action!r}"))

        except Exception as exc:
            print(f"budget_governor_py component error: {exc}")
            return Response(500, {"content-type": "application/json"}, _error_json("internal error"))


# Mandatory export for spin-sdk v4
if _SPIN_AVAILABLE:
    incoming_handler = HttpHandler()
