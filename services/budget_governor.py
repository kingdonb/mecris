"""
Budget Governor — Fiscal Intelligence layer for Mecris.

Manages multi-bucket LLM quotas with:
- 5%/5% Rate Envelope: In any rolling 39-minute window, no more than 5% of a
  bucket's period quota may be spent.
- Helix Inversion: SPEND buckets (Helix, Gemini) are encouraged; GUARD buckets
  (Anthropic, Groq) are rationed.
- Live Helix balance discovery via the Helix API.

Plan: yebyen/mecris#26
"""
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger("mecris.services.budget_governor")

try:
    import requests
except ImportError:
    requests = None  # type: ignore


class BucketType(Enum):
    GUARD = "guard"   # Ration these (Anthropic, Groq — real money)
    SPEND = "spend"   # Use these up (Helix, Gemini — use-it-or-lose-it)


# 5% of 13-hour daylight window (780 minutes) = 39 minutes
_DAYLIGHT_MINUTES = 780
_ENVELOPE_WINDOW_MINUTES = int(_DAYLIGHT_MINUTES * 0.05)  # 39 min
_ENVELOPE_SPEND_RATIO = 0.05  # 5% of period quota per window


class BudgetGovernor:
    """
    Controls LLM spending across multiple providers.

    Buckets are defined at instantiation. Spend events are logged in-memory;
    this is intentionally lightweight — no DB dependency.
    """

    def __init__(self):
        self.buckets: Dict[str, Dict[str, Any]] = {
            "helix": {
                "type": BucketType.SPEND,
                "limit": float(os.getenv("HELIX_CREDIT_LIMIT", "100.00")),
                "description": "Helix SaaS credits (use-it-or-lose-it)",
            },
            "gemini": {
                "type": BucketType.SPEND,
                "limit": float(os.getenv("GEMINI_FREE_LIMIT", "50.00")),
                "description": "Gemini free-tier credits (use-it-or-lose-it)",
            },
            "anthropic_api": {
                "type": BucketType.GUARD,
                "limit": float(os.getenv("ANTHROPIC_BUDGET_LIMIT", "20.89")),
                "description": "Anthropic paid API (ration carefully)",
            },
            "groq": {
                "type": BucketType.GUARD,
                "limit": float(os.getenv("GROQ_BUDGET_LIMIT", "10.00")),
                "description": "Groq API (ration carefully)",
            },
        }
        # Spend log: list of dicts with keys: bucket, cost, ts
        self._spend_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Core envelope logic
    # ------------------------------------------------------------------

    def _total_spent(self, bucket_name: str) -> float:
        """Sum all spend events for a bucket across all time."""
        return sum(
            e["cost"] for e in self._spend_log if e["bucket"] == bucket_name
        )

    def _window_spent(self, bucket_name: str) -> float:
        """Sum spend events for a bucket in the last 39-minute rolling window."""
        cutoff = datetime.utcnow() - timedelta(minutes=_ENVELOPE_WINDOW_MINUTES)
        return sum(
            e["cost"]
            for e in self._spend_log
            if e["bucket"] == bucket_name and e["ts"] >= cutoff
        )

    def check_envelope(self, bucket_name: str, cost_estimate: float) -> str:
        """
        Returns 'allow', 'defer', or 'deny' based on the 5%/5% rule.

        - 'deny'  : total spend already at or above the period limit.
        - 'defer' : within the rolling 39-min window, adding this cost would
                    exceed 5% of the period quota.
        - 'allow' : safe to proceed.
        """
        if bucket_name not in self.buckets:
            raise ValueError(f"Unknown bucket: {bucket_name!r}")

        cfg = self.buckets[bucket_name]
        limit = cfg["limit"]

        # Hard stop: total exhausted
        if self._total_spent(bucket_name) >= limit:
            return "deny"

        # Rate envelope: rolling window cap
        window_cap = _ENVELOPE_SPEND_RATIO * limit
        if self._window_spent(bucket_name) + cost_estimate > window_cap:
            return "defer"

        return "allow"

    def record_spend(self, bucket_name: str, cost: float) -> None:
        """Record an actual spend event for rate tracking."""
        if bucket_name not in self.buckets:
            raise ValueError(f"Unknown bucket: {bucket_name!r}")
        self._spend_log.append({
            "bucket": bucket_name,
            "cost": cost,
            "ts": datetime.utcnow(),
        })

    # ------------------------------------------------------------------
    # Routing recommendation
    # ------------------------------------------------------------------

    def recommend_bucket(self, task_type: str = "general") -> str:
        """
        Returns the name of the best available bucket.

        Priority:
          1. SPEND buckets that are not exhausted (Helix Inversion — use them up).
          2. GUARD buckets that are not exhausted (fallback).
          3. Least-spent GUARD bucket (emergency fallback when all are tight).
        """
        spend_available = [
            name for name, cfg in self.buckets.items()
            if cfg["type"] == BucketType.SPEND
            and self._total_spent(name) < cfg["limit"]
        ]
        if spend_available:
            # Prefer the one with the most remaining credits
            return max(
                spend_available,
                key=lambda n: self.buckets[n]["limit"] - self._total_spent(n),
            )

        guard_available = [
            name for name, cfg in self.buckets.items()
            if cfg["type"] == BucketType.GUARD
            and self._total_spent(name) < cfg["limit"]
        ]
        if guard_available:
            return min(
                guard_available,
                key=lambda n: self._total_spent(n) / self.buckets[n]["limit"],
            )

        # All exhausted — return the GUARD bucket with the most remaining
        return min(
            self.buckets.keys(),
            key=lambda n: self._total_spent(n) / self.buckets[n]["limit"],
        )

    # ------------------------------------------------------------------
    # Status report
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """
        Returns a dict suitable for the MCP tool response:
          - buckets: per-bucket consumption and envelope status
          - recommendation: best bucket for next task
          - envelope_status: overall system state
        """
        bucket_report: Dict[str, Any] = {}
        all_denied = True

        for name, cfg in self.buckets.items():
            spent = self._total_spent(name)
            window = self._window_spent(name)
            limit = cfg["limit"]
            envelope = self.check_envelope(name, 0.01)
            if envelope != "deny":
                all_denied = False

            bucket_report[name] = {
                "type": cfg["type"].value,
                "limit": limit,
                "spent_total": round(spent, 4),
                "spent_window_39min": round(window, 4),
                "remaining": round(max(0.0, limit - spent), 4),
                "envelope": envelope,
                "description": cfg.get("description", ""),
            }

        helix_live = self.get_helix_balance()
        if helix_live is not None:
            bucket_report["helix"]["live_balance"] = helix_live

        return {
            "buckets": bucket_report,
            "recommendation": self.recommend_bucket(),
            "envelope_status": "HALTED" if all_denied else "OK",
            "window_minutes": _ENVELOPE_WINDOW_MINUTES,
            "envelope_spend_pct": int(_ENVELOPE_SPEND_RATIO * 100),
        }

    # ------------------------------------------------------------------
    # Helix API discovery
    # ------------------------------------------------------------------

    def get_helix_balance(self) -> Optional[float]:
        """
        Attempt to fetch live Helix credit balance.

        Uses ANTHROPIC_BASE_URL (pointing to Helix) and ANTHROPIC_API_KEY.
        Returns a float if successful, None if the API is unreachable or
        the response doesn't contain a parseable balance.
        """
        if requests is None:
            logger.warning("requests library not available; skipping Helix balance fetch.")
            return None

        base_url = os.getenv("ANTHROPIC_BASE_URL", "").rstrip("/")
        api_key = os.getenv("ANTHROPIC_API_KEY", "")

        if not base_url or not api_key:
            logger.debug("ANTHROPIC_BASE_URL or ANTHROPIC_API_KEY not set; skipping Helix fetch.")
            return None

        # Helix API reference: https://docs.helixml.tech/helix/api-reference/
        # Try the /api/v1/apps endpoint as suggested in guidance; look for balance field.
        try:
            resp = requests.get(
                f"{base_url}/api/v1/me",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                balance = data.get("balance") or data.get("credit_balance")
                if balance is not None:
                    return float(balance)
                logger.debug("Helix /api/v1/me: balance key not found in response")
            else:
                logger.debug("Helix /api/v1/me returned status %s", resp.status_code)
        except Exception as exc:
            logger.debug("Helix balance fetch failed: %s", exc)

        return None
