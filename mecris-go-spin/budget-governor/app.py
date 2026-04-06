"""
Budget Governor WASM component — app.py (Fiscal Intelligence)

HTTP handlers:
- GET /internal/budget-status?user_id=<id>
- POST /internal/budget-gate?user_id=<id>&bucket=<name>&cost=<n>
- POST /internal/budget-record?user_id=<id>&bucket=<name>&cost=<n>

Implementation: componentize-py + spin_sdk (KV store, outbound HTTP).
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("mecris.budget_governor_component")

# 5% of 13-hour daylight window (780 minutes) = 39 minutes
_ENVELOPE_WINDOW_MINUTES = 39
_ENVELOPE_SPEND_RATIO = 0.05

class BudgetGovernor:
    def __init__(self, user_id: str, kv_store, variables):
        self.user_id = user_id
        self.kv_store = kv_store
        self.variables = variables
        self.buckets = {
            "helix": {"type": "spend", "limit": float(variables.get("HELIX_CREDIT_LIMIT") or "100.00")},
            "gemini": {"type": "spend", "limit": float(variables.get("GEMINI_FREE_LIMIT") or "50.00")},
            "anthropic_api": {"type": "guard", "limit": float(variables.get("ANTHROPIC_BUDGET_LIMIT") or "20.89")},
            "groq": {"type": "guard", "limit": float(variables.get("GROQ_BUDGET_LIMIT") or "10.00")},
        }
        self.kv_key = f"budget_log_{user_id}"
        self._spend_log = self._load_log()

    def _load_log(self):
        try:
            val = self.kv_store.get(self.kv_key)
            if not val: return []
            raw = json.loads(val.decode())
            return [{"bucket": e["bucket"], "cost": float(e["cost"]), "ts": e["ts"]} for e in raw]
        except: return []

    def _save_log(self):
        try:
            # Keep only last 24 hours of logs to prevent KV bloat
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            self._spend_log = [e for e in self._spend_log if e["ts"] >= cutoff]
            self.kv_store.set(self.kv_key, json.dumps(self._spend_log).encode())
        except: pass

    def _total_spent(self, bucket: str):
        return sum(e["cost"] for e in self._spend_log if e["bucket"] == bucket)

    def _window_spent(self, bucket: str):
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=_ENVELOPE_WINDOW_MINUTES)).isoformat()
        return sum(e["cost"] for e in self._spend_log if e["bucket"] == bucket and e["ts"] >= cutoff)

    def check_envelope(self, bucket: str, cost: float):
        if bucket not in self.buckets: return "deny"
        limit = self.buckets[bucket]["limit"]
        if self._total_spent(bucket) >= limit: return "deny"
        if self._window_spent(bucket) + cost > (_ENVELOPE_SPEND_RATIO * limit): return "defer"
        return "allow"

    def record_spend(self, bucket: str, cost: float):
        if bucket in self.buckets:
            self._spend_log.append({"bucket": bucket, "cost": cost, "ts": datetime.now(timezone.utc).isoformat()})
            self._save_log()

    def recommend_bucket(self):
        spend_avail = [n for n, c in self.buckets.items() if c["type"] == "spend" and self._total_spent(n) < c["limit"]]
        if spend_avail: return max(spend_avail, key=lambda n: self.buckets[n]["limit"] - self._total_spent(n))
        guard_avail = [n for n, c in self.buckets.items() if c["type"] == "guard" and self._total_spent(n) < c["limit"]]
        if guard_avail: return min(guard_avail, key=lambda n: self._total_spent(n) / self.buckets[n]["limit"])
        return min(self.buckets.keys(), key=lambda n: self._total_spent(n) / self.buckets[n]["limit"])

    def get_status(self):
        report = {}
        for name, cfg in self.buckets.items():
            spent = self._total_spent(name)
            report[name] = {
                "type": cfg["type"], "limit": cfg["limit"], "spent_total": round(spent, 4),
                "spent_window": round(self._window_spent(name), 4), "remaining": round(max(0.0, cfg["limit"] - spent), 4),
                "envelope": self.check_envelope(name, 0.01)
            }
        return {"buckets": report, "recommendation": self.recommend_bucket(), "window_minutes": _ENVELOPE_WINDOW_MINUTES}

def _parse_params(path: str):
    if "?" not in path: return {}
    return {k: v[0] for k, v in parse_qs(path.split("?", 1)[1]).items() if v}

try:
    from spin_sdk.http import IncomingHandler as _SpinHandler, Request, Response
    from spin_sdk import variables as _vars, key_value as _kv

    class IncomingHandler(_SpinHandler):
        def handle(self, request: Request) -> Response:
            params = _parse_params(request.uri)
            user_id = params.get("user_id")
            if not user_id: return Response(400, body=b"user_id required")
            
            store = _kv.Store.open_default()
            gov = BudgetGovernor(user_id, store, _vars)
            
            path = request.uri.split("?")[0]
            if "/internal/budget-status" in path:
                return Response(200, {"content-type": "application/json"}, json.dumps(gov.get_status()).encode())
            
            elif "/internal/budget-gate" in path:
                bucket = params.get("bucket")
                cost = float(params.get("cost") or "0.01")
                env = gov.check_envelope(bucket, cost)
                return Response(200, {"content-type": "application/json"}, json.dumps({
                    "allowed": env != "deny", "envelope": env, "recommendation": gov.recommend_bucket()
                }).encode())
                
            elif "/internal/budget-record" in path:
                bucket = params.get("bucket")
                cost = float(params.get("cost") or "0.0")
                gov.record_spend(bucket, cost)
                return Response(200, body=b"recorded")

            return Response(404)

    def handle_request(request): return IncomingHandler().handle(request)
except ImportError:
    def handle_request(request): raise NotImplementedError()
