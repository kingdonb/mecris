"""Helix billing reader — task 588 lever C1a (Type 1, latent).

Reads the org's live Helix credit wallet. The billing endpoint was pinned by
the M1 door-trace (2026-09-19, design.md §9 of task 588):

    GET {base}/api/v1/wallet?org_id={org}
    -> {"balance": <float USD>,
        "subscription_current_period_start": <epoch s>,
        "subscription_current_period_end":   <epoch s>,  # next grant day
        "org_id": ..., "subscription_status": ...}

Headless auth (no cookies): ``Authorization: Bearer <hl- API key>``.
Environment:
  HELIX_BILLING_API_TOKEN   read-only Helix API key (fallback: USER_API_TOKEN,
                            which is what a Helix sandbox already exports)
  HELIX_API_BASE_URL        default https://app.helix.ml
  HELIX_BILLING_ORG_ID      default "mecris"

Operator caveat learned at M1: Cloudflare fronts app.helix.ml and answers 403
``error code: 1010`` to requests whose User-Agent smells like a default Python
client. We send a neutral UA and ``Accept: application/json`` — never the
library default.

Contract: this module never raises to its caller and a failed fetch never
masquerades as a number — any failure path returns ``None`` (R2/R6: upstream
must be able to tell "unknown" from "$0"). A genuine 0.0 balance passes
through as 0.0, not None.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

try:
    import requests
except ImportError:  # mirror budget_governor.py's optional-dependency pattern
    requests = None

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://app.helix.ml"
DEFAULT_ORG_ID = "mecris"
CACHE_TTL_SECONDS = 300  # 5-minute cache (design.md §3, C1a)

# Do not "improve" this toward the library default: Cloudflare 1010 bans it.
_HEADERS_UA = "helix-billing-lever/1.0 (Mecris; task-588)"

# org_id -> (monotonic_ts, wallet dict). Process-local; single leader runs it.
_CACHE: dict = {}


def _auth_token() -> str:
    return os.getenv("HELIX_BILLING_API_TOKEN") or os.getenv("USER_API_TOKEN") or ""


def _base_url() -> str:
    return os.getenv("HELIX_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _org_id() -> str:
    return os.getenv("HELIX_BILLING_ORG_ID", DEFAULT_ORG_ID)


def clear_cache() -> None:
    """Drop cached wallet readings (tests / manual re-probe)."""
    _CACHE.clear()


def get_wallet(force: bool = False) -> Optional[dict]:
    """
    Fetch the org's wallet dict (5-min cached).

    Returns None on any failure: missing config, no requests lib, network
    error, non-200, or unparsable body. Never raises.
    """
    if requests is None:
        logger.warning("requests library not available; skipping Helix wallet fetch.")
        return None

    org = _org_id()
    now = time.monotonic()
    cached = _CACHE.get(org)
    if cached and not force and (now - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    token = _auth_token()
    if not token:
        logger.debug("No Helix billing token set; skipping wallet fetch.")
        return None

    url = f"{_base_url()}/api/v1/wallet"
    try:
        resp = requests.get(
            url,
            params={"org_id": org},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": _HEADERS_UA,
            },
            timeout=5,
        )
        if resp.status_code != 200:
            logger.debug("Helix /api/v1/wallet returned status %s", resp.status_code)
            return None
        data = resp.json()
        if not isinstance(data, dict) or data.get("balance") is None:
            logger.debug("Helix wallet response has no parseable 'balance' key")
            return None
        wallet = {
            "balance": float(data["balance"]),
            "org_id": data.get("org_id", org),
            "period_start": data.get("subscription_current_period_start"),
            "period_end": data.get("subscription_current_period_end"),
            "subscription_status": data.get("subscription_status"),
            "fetched_at": now,
        }
        _CACHE[org] = (now, wallet)
        return wallet
    except Exception as exc:  # noqa: BLE001 — by contract: nothing escapes
        logger.debug("Helix wallet fetch failed: %s", exc)
        return None


def get_balance(force: bool = False) -> Optional[float]:
    """
    Live Helix balance in USD, or None if unknown. A true zero returns 0.0.
    """
    wallet = get_wallet(force=force)
    if wallet is None:
        return None
    return wallet["balance"]


if __name__ == "__main__":  # hand-driven proof: `python scripts/helix_billing.py`
    logging.basicConfig(level=logging.INFO)
    w = get_wallet(force=True)
    if w:
        print(f"balance=${w['balance']:.4f} org={w['org_id']} status={w['subscription_status']}")
        if w.get("period_end"):
            print("period_end epoch:", w["period_end"])
    else:
        print("wallet fetch failed (see debug logging)")
