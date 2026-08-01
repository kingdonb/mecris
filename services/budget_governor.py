"""
WARNING: DEPRECATED LEGACY FILE

This local logic has been vacuumed into the Fermyon Cloud.
The single source of truth for the Budget Governor is now the WASM
component located in `poc/wasm/budget-governor-py/`. 

DO NOT MODIFY this file for logic updates. It is kept only for
historical reference until the local MCP server finishes the transition.
"""
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
from datetime import datetime, timedelta, timezone
import json
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

    def __init__(self, spend_log_path: Optional[str] = None):
        self.buckets: Dict[str, Dict[str, Any]] = {
            "helix": {
                "type": BucketType.SPEND,
                "limit": float(os.getenv("HELIX_CREDIT_LIMIT", "100.00")),
                "description": "Helix SaaS credits (use-it-or-lose-it)",
                "unit": "dollars",
            },
            "gemini": {
                "type": BucketType.SPEND,
                "limit": float(os.getenv("GEMINI_FREE_LIMIT", "50.00")),
                "description": "Gemini free-tier credits (use-it-or-lose-it)",
                "unit": "dollars",
            },
            "anthropic_api": {
                "type": BucketType.GUARD,
                "limit": float(os.getenv("ANTHROPIC_BUDGET_LIMIT", "20.89")),
                "description": "Anthropic paid API (ration carefully)",
                "unit": "dollars",
            },
            "groq": {
                "type": BucketType.GUARD,
                "limit": float(os.getenv("GROQ_BUDGET_LIMIT", "10.00")),
                "description": "Groq API (ration carefully)",
                "unit": "dollars",
            },
            "openrouter": {
                "type": BucketType.GUARD,
                "limit": float(os.getenv("OPENROUTER_DOLLAR_LIMIT", "10.00")),
                "description": "OpenRouter paid API ($10 limit)",
                "unit": "dollars",
            },
            "openrouter_requests": {
                "type": BucketType.GUARD,
                "limit": float(os.getenv("OPENROUTER_REQUEST_LIMIT", "1000.0")),
                "description": "OpenRouter free tier: 1000 req/day (resets midnight UTC)",
                "unit": "requests",
                "reset_cron": "0 0 * * *",
            },
        }
        self._spend_log_path: Optional[str] = spend_log_path
        # Spend log: list of dicts with keys: bucket, cost, ts
        self._spend_log: List[Dict[str, Any]] = self._load_spend_log()

    def _load_spend_log(self) -> List[Dict[str, Any]]:
        """Load spend events from JSON file. Returns empty list on any error."""
        if not self._spend_log_path:
            return []
        try:
            with open(self._spend_log_path, "r") as f:
                raw = json.load(f)
            result = []
            for entry in raw:
                result.append({
                    "bucket": entry["bucket"],
                    "cost": float(entry["cost"]),
                    "ts": datetime.fromisoformat(entry["ts"]),
                })
            return result
        except FileNotFoundError:
            return []
        except Exception as exc:
            logger.warning("Could not load spend log from %s: %s — starting fresh.", self._spend_log_path, exc)
            return []

    def _persist_spend_log(self) -> None:
        """Write the current spend log to disk as JSON."""
        if not self._spend_log_path:
            return
        try:
            serializable = [
                {"bucket": e["bucket"], "cost": e["cost"], "ts": e["ts"].isoformat()}
                for e in self._spend_log
            ]
            with open(self._spend_log_path, "w") as f:
                json.dump(serializable, f)
        except Exception as exc:
            logger.warning("Could not persist spend log to %s: %s", self._spend_log_path, exc)

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
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=_ENVELOPE_WINDOW_MINUTES)
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
            "ts": datetime.now(timezone.utc),
        })
        self._persist_spend_log()

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
    # Narrator context summary
    # ------------------------------------------------------------------

    def get_narrator_summary(self) -> Dict[str, Any]:
        """
        Returns a slim dict suitable for embedding in get_narrator_context().

        Keys:
          - routing_recommendation: name of the best bucket to use now
          - envelope_status: 'OK' or 'HALTED'
        """
        status = self.get_status()
        return {
            "routing_recommendation": status["recommendation"],
            "envelope_status": status["envelope_status"],
        }

    # ------------------------------------------------------------------
    # Enforcement gate
    # ------------------------------------------------------------------

    def budget_gate(self, bucket: str, cost_estimate: float = 0.01) -> Optional[Dict[str, Any]]:
        """
        Enforcement guard for cost-incurring MCP handlers.

        Returns None if the call should proceed, or an error dict if it should
        be blocked (bucket envelope is 'deny' — total spend at or above limit).

        Only blocks on 'deny' (hard stop), not on 'defer' (rate throttle),
        so normal session use is not disrupted by short-window spikes.

        Usage in handlers::

            guard = _budget_governor.budget_gate("anthropic_api")
            if guard:
                return guard
            # ... rest of handler
        """
        result = self.check_envelope(bucket, cost_estimate)
        if result == "deny":
            recommendation = self.recommend_bucket()
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
            recommendation = self.recommend_bucket()
            logger.warning(
                "Budget DEFER for bucket '%s': 39-min rate envelope is full. "
                "Proceeding but flagging caller.",
                bucket,
            )
            return {
                "budget_halted": False,
                "warning": (
                    f"Budget DEFER for bucket '{bucket}': rate envelope is full "
                    f"(>5%% of quota spent in last 39 min). "
                    f"Consider routing to: {recommendation}"
                ),
                "bucket": bucket,
                "envelope": result,
                "routing_recommendation": recommendation,
            }
        return None

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


# ------------------------------------------------------------------
# Neon-backed Budget Governor (Phase 2: MCP exposure)
# ------------------------------------------------------------------

class NeonBudgetGovernor:
    """
    Budget Governor with Neon PostgreSQL persistence.
    
    Replaces the JSON file backend with a proper database table.
    Uses the same envelope logic (5%/5% rule) as BudgetGovernor.
    """
    
    def __init__(self, neon_url: Optional[str] = None, user_id: Optional[str] = None):
        self.neon_url = neon_url or os.getenv("NEON_DB_URL")
        self.user_id = user_id or os.getenv("DEFAULT_USER_ID", "yebyen")
        
        # Bucket configuration (same as BudgetGovernor)
        self.buckets: Dict[str, Dict[str, Any]] = {
            "helix": {
                "type": BucketType.SPEND,
                "limit": float(os.getenv("HELIX_CREDIT_LIMIT", "100.00")),
                "description": "Helix SaaS credits (use-it-or-lose-it)",
                "unit": "dollars",
            },
            "gemini": {
                "type": BucketType.SPEND,
                "limit": float(os.getenv("GEMINI_FREE_LIMIT", "50.00")),
                "description": "Gemini free-tier credits (use-it-or-lose-it)",
                "unit": "dollars",
            },
            "anthropic_api": {
                "type": BucketType.GUARD,
                "limit": float(os.getenv("ANTHROPIC_BUDGET_LIMIT", "20.89")),
                "description": "Anthropic paid API (ration carefully)",
                "unit": "dollars",
            },
            "groq": {
                "type": BucketType.GUARD,
                "limit": float(os.getenv("GROQ_BUDGET_LIMIT", "10.00")),
                "description": "Groq API (ration carefully)",
                "unit": "dollars",
            },
            "openrouter": {
                "type": BucketType.GUARD,
                "limit": float(os.getenv("OPENROUTER_DOLLAR_LIMIT", "10.00")),
                "description": "OpenRouter paid API ($10 limit)",
                "unit": "dollars",
            },
            "openrouter_requests": {
                "type": BucketType.GUARD,
                "limit": float(os.getenv("OPENROUTER_REQUEST_LIMIT", "1000.0")),
                "description": "OpenRouter free tier: 1000 req/day (resets midnight UTC)",
                "unit": "requests",
                "reset_cron": "0 0 * * *",
            },
        }
        
        if not self.neon_url:
            logger.warning("NEON_DB_URL not set; NeonBudgetGovernor will fail on DB operations.")
        else:
            self._init_db()
    
    def _init_db(self):
        """Create the spend_log table if it doesn't exist."""
        try:
            import psycopg2
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS budget_governor_spend_log (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            bucket TEXT NOT NULL,
                            cost DOUBLE PRECISION NOT NULL,
                            ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                        CREATE INDEX IF NOT EXISTS idx_budget_governor_spend_log_user_bucket_ts
                            ON budget_governor_spend_log (user_id, bucket, ts);
                    """)
        except Exception as exc:
            logger.error(f"NeonBudgetGovernor: DB init failed: {exc}")
            raise
    
    def _load_spend_log(self) -> List[Dict[str, Any]]:
        """Load all spend events for this user from Neon."""
        if not self.neon_url:
            return []
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT bucket, cost, ts
                        FROM budget_governor_spend_log
                        WHERE user_id = %s
                        ORDER BY ts ASC
                    """, (self.user_id,))
                    rows = cur.fetchall()
                    return [
                        {"bucket": r["bucket"], "cost": float(r["cost"]), "ts": r["ts"]}
                        for r in rows
                    ]
        except Exception as exc:
            logger.error(f"NeonBudgetGovernor: load spend log failed: {exc}")
            return []
    
    def _persist_spend(self, bucket: str, cost: float, ts: datetime) -> None:
        """Insert a single spend event into Neon."""
        if not self.neon_url:
            return
        try:
            import psycopg2
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO budget_governor_spend_log (user_id, bucket, cost, ts)
                        VALUES (%s, %s, %s, %s)
                    """, (self.user_id, bucket, cost, ts))
        except Exception as exc:
            logger.error(f"NeonBudgetGovernor: persist spend failed: {exc}")
            raise

    # Core envelope logic (mirrors BudgetGovernor)
    
    def _total_spent(self, bucket_name: str, spend_log: Optional[List[Dict[str, Any]]] = None) -> float:
        """Sum all spend events for a bucket across all time."""
        log = spend_log if spend_log is not None else self._load_spend_log()
        return sum(
            e["cost"] for e in log if e["bucket"] == bucket_name
        )

    def _window_spent(self, bucket_name: str, spend_log: Optional[List[Dict[str, Any]]] = None) -> float:
        """Sum spend events for a bucket in the last 39-minute rolling window."""
        log = spend_log if spend_log is not None else self._load_spend_log()
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=_ENVELOPE_WINDOW_MINUTES)
        return sum(
            e["cost"]
            for e in log
            if e["bucket"] == bucket_name and e["ts"] >= cutoff
        )

    def check_envelope(self, bucket_name: str, cost_estimate: float) -> str:
        """
        Returns 'allow', 'defer', or 'deny' based on the 5%/5% rule.
        - 'deny': total spend already at or above the period limit.
        - 'defer': within the rolling 39-min window, adding this cost would
                   exceed 5% of the period quota.
        - 'allow': safe to proceed.
        """
        if bucket_name not in self.buckets:
            raise ValueError(f"Unknown bucket: {bucket_name!r}")

        cfg = self.buckets[bucket_name]
        limit = cfg["limit"]
        spend_log = self._load_spend_log()

        # Hard stop: total exhausted
        if self._total_spent(bucket_name, spend_log) >= limit:
            return "deny"

        # Rate envelope: rolling window cap
        window_cap = _ENVELOPE_SPEND_RATIO * limit
        if self._window_spent(bucket_name, spend_log) + cost_estimate > window_cap:
            return "defer"

        return "allow"

    def record_spend(self, bucket_name: str, cost: float) -> None:
        """Record an actual spend event for rate tracking."""
        if bucket_name not in self.buckets:
            raise ValueError(f"Unknown bucket: {bucket_name!r}")
        ts = datetime.now(timezone.utc)
        self._persist_spend(bucket_name, cost, ts)

    # Routing recommendation
    
    def recommend_bucket(self, task_type: str = "general") -> str:
        """
        Returns the name of the best available bucket.
        Priority:
          1. SPEND buckets that are not exhausted (Helix Inversion — use them up).
          2. GUARD buckets that are not exhausted (fallback).
          3. Least-spent GUARD bucket (emergency fallback when all are tight).
        """
        spend_log = self._load_spend_log()
        spend_available = [
            name for name, cfg in self.buckets.items()
            if cfg["type"] == BucketType.SPEND
            and self._total_spent(name, spend_log) < cfg["limit"]
        ]
        if spend_available:
            return max(
                spend_available,
                key=lambda n: self.buckets[n]["limit"] - self._total_spent(n, spend_log),
            )

        guard_available = [
            name for name, cfg in self.buckets.items()
            if cfg["type"] == BucketType.GUARD
            and self._total_spent(name, spend_log) < cfg["limit"]
        ]
        if guard_available:
            return min(
                guard_available,
                key=lambda n: self._total_spent(n, spend_log) / self.buckets[n]["limit"],
            )

        return min(
            self.buckets.keys(),
            key=lambda n: self._total_spent(n, spend_log) / self.buckets[n]["limit"],
        )

    # Status report
    
    def get_status(self) -> Dict[str, Any]:
        """
        Returns a dict suitable for the MCP tool response:
          - buckets: per-bucket consumption and envelope status
          - recommendation: best bucket for next task
          - envelope_status: overall system state
        """
        spend_log = self._load_spend_log()
        bucket_report: Dict[str, Any] = {}
        all_denied = True

        for name, cfg in self.buckets.items():
            spent = self._total_spent(name, spend_log)
            window = self._window_spent(name, spend_log)
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

    # Narrator context summary
    
    def get_narrator_summary(self) -> Dict[str, Any]:
        """
        Returns a slim dict suitable for embedding in get_narrator_context().
        Keys:
          - routing_recommendation: name of the best bucket to use now
          - envelope_status: 'OK' or 'HALTED'
        """
        status = self.get_status()
        return {
            "routing_recommendation": status["recommendation"],
            "envelope_status": status["envelope_status"],
        }

    # Enforcement gate
    
    def budget_gate(self, bucket: str, cost_estimate: float = 0.01) -> Optional[Dict[str, Any]]:
        """
        Enforcement guard for cost-incurring MCP handlers.
        Returns None if the call should proceed, or an error dict if it should
        be blocked (bucket envelope is 'deny' — total spend at or above limit).
        Only blocks on 'deny' (hard stop), not on 'defer' (rate throttle),
        so normal session use is not disrupted by short-window spikes.
        """
        result = self.check_envelope(bucket, cost_estimate)
        if result == "deny":
            recommendation = self.recommend_bucket()
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
            recommendation = self.recommend_bucket()
            logger.warning(
                "Budget DEFER for bucket '%s': 39-min rate envelope is full. "
                "Proceeding but flagging caller.",
                bucket,
            )
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

    # Helix API discovery (inherited from BudgetGovernor)

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
