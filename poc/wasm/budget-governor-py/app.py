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
from datetime import datetime
from typing import List, Dict, Any, Optional

from spin_sdk import http, variables
from spin_sdk.http import Request, Response
import spin_sdk.key_value as kv

logger = logging.getLogger("mecris.budget_governor_component")

# ---------------------------------------------------------------------------
# Pure Logic & Data Models
# ---------------------------------------------------------------------------

_KV_SPEND_LOG_KEY = "budget_spend_log"

def make_bucket_config(limits: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    config = {}
    for bucket, limit in limits.items():
        config[bucket] = {
            "soft_limit": limit * 0.05,
            "hard_limit": limit * 0.05,
            "total_budget": limit,
        }
    return config

def get_rolling_24h_spend(spend_log: List[Dict[str, Any]], bucket_name: str) -> float:
    now = datetime.utcnow()
    total = 0.0
    for entry in spend_log:
        if entry["bucket"] == bucket_name:
            ts = datetime.fromisoformat(entry["ts"])
            if (now - ts).total_seconds() <= 86400:
                total += entry["cost"]
    return total

def check_envelope(spend_log: List[Dict[str, Any]], bucket_config: Dict[str, Any], bucket_name: str, incoming_cost: float) -> str:
    if bucket_name not in bucket_config:
        return "allowed"
    
    current_spend = get_rolling_24h_spend(spend_log, bucket_name)
    limits = bucket_config[bucket_name]
    
    if (current_spend + incoming_cost) > limits["hard_limit"]:
        return "blocked"
    if (current_spend + incoming_cost) > limits["soft_limit"]:
        return "throttled"
    return "allowed"

def budget_gate(spend_log: List[Dict[str, Any]], bucket_config: Dict[str, Any], bucket_name: str, incoming_cost: float) -> Optional[Dict[str, Any]]:
    envelope = check_envelope(spend_log, bucket_config, bucket_name, incoming_cost)
    if envelope == "blocked":
        return {"allowed": False, "reason": "hard_limit_exceeded", "bucket": bucket_name}
    return None

def recommend_bucket(spend_log: List[Dict[str, Any]], bucket_config: Dict[str, Any]) -> str:
    options = ["anthropic_api", "groq"]
    for opt in options:
        if check_envelope(spend_log, bucket_config, opt, 0.0) == "allowed":
            return opt
    return "groq"

def get_status(spend_log: List[Dict[str, Any]], bucket_config: Dict[str, Any], helix_balance: Optional[float]) -> Dict[str, Any]:
    status = {"buckets": {}, "helix_balance": helix_balance}
    for bucket, limits in bucket_config.items():
        spend = get_rolling_24h_spend(spend_log, bucket)
        status["buckets"][bucket] = {
            "spend_24h": spend,
            "soft_limit": limits["soft_limit"],
            "hard_limit": limits["hard_limit"],
            "envelope": check_envelope(spend_log, bucket_config, bucket, 0.0)
        }
    return status

# ---------------------------------------------------------------------------
# WASM Infrastructure Helpers
# ---------------------------------------------------------------------------

def _load_spend_log_from_json(raw_bytes: Optional[bytes]) -> List[Dict[str, Any]]:
    if not raw_bytes:
        return []
    try:
        return json.loads(raw_bytes)
    except Exception:
        return []

def _dump_spend_log_to_json(spend_log: List[Dict[str, Any]]) -> bytes:
    serializable = spend_log[-200:] # Keep last 200 entries to prevent KV bloat
    return json.dumps(serializable).encode()

def _parse_request(body_bytes: bytes) -> Dict[str, Any]:
    try:
        data = json.loads(body_bytes or b"{}")
    except Exception:
        data = {}
    return {
        "action": str(data.get("action", "status")),
        "bucket": str(data.get("bucket", "")),
        "cost": float(data.get("cost", 0.0))
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
    return make_bucket_config(limits)

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
incoming_handler = HttpHandler()
