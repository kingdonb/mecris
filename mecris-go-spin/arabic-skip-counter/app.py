"""
arabic-skip-counter WASM component — app.py

Implements the WIT world `arabic-skip-counter` via componentize-py.
At runtime this module runs inside CPython embedded in WASM; outbound HTTP
is satisfied by the WASI sockets layer (Spin provides this).

The logic mirrors services/arabic_skip_counter.py exactly.  Keeping it
self-contained avoids a dependency on the repo layout at component-build time.
"""

import base64
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

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
        if rows:
            return int(rows[0].get("count", 0))
        return 0
    except Exception as e:
        logger.error(f"arabic_skip_counter component: HTTP query failed: {e}")
        return 0


class WitWorld:
    """Concrete implementation of the arabic-skip-counter WIT world."""

    def count_arabic_reminders(self, neon_url: str, user_id: str, hours: int) -> int:
        return _count_reminders(neon_url, user_id, hours)
