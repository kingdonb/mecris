"""
arabic_skip_counter.py — Counts consecutive ignored Arabic review cycles.

Queries message_log for arabic_review_reminder and arabic_review_escalation
rows sent within the last N hours. Used as the skip_count_provider for
ReminderService Phase 3 escalation.

Uses the Neon HTTP API (/sql endpoint via httpx) instead of psycopg2, so the
module has zero native-driver dependencies and is ready for componentize-py
wrapping (Phase 1.5b).
"""

import base64
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

logger = logging.getLogger("mecris.services.arabic_skip_counter")

_ARABIC_REMINDER_TYPES = ("arabic_review_reminder", "arabic_review_escalation")

_SQL = (
    "SELECT COUNT(*) FROM message_log"
    " WHERE (type = $1 OR type = $2) AND user_id = $3 AND sent_at >= $4"
)


def _http_url_and_auth(neon_url: str) -> tuple[str, str]:
    """Derive Neon HTTP endpoint URL and Basic auth token from a postgres:// URL."""
    parsed = urlparse(neon_url)
    host = parsed.hostname or ""
    user = parsed.username or ""
    password = parsed.password or ""
    http_url = f"https://{host}/sql"
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return http_url, token


def count_arabic_reminders(neon_url: str, user_id: str, hours: int = 24) -> int:
    """Count Arabic reminder messages sent to user_id in the last `hours` hours.

    Returns an int — the number of arabic_review_reminder / arabic_review_escalation
    rows in message_log within the window. This is a proxy for consecutive ignored
    cycles: each fired reminder that wasn't followed by cards done counts as one skip.

    Uses the Neon HTTP API (/sql endpoint) instead of psycopg2.
    Returns 0 on any error (fail-safe: no escalation rather than false escalation).
    """
    import httpx  # lazy import: not installed in all environments

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
        logger.error(f"arabic_skip_counter: HTTP query failed: {e}")
        return 0
