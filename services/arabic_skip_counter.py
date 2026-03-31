"""
arabic_skip_counter.py — Counts consecutive ignored Arabic review cycles.

Queries message_log for arabic_review_reminder and arabic_review_escalation
rows sent within the last N hours. Used as the skip_count_provider for
ReminderService Phase 3 escalation.

Extracted as a standalone module so it can be unit-tested without importing
mcp_server.py (which requires MCP SDK, FastAPI, and other heavy dependencies).
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger("mecris.services.arabic_skip_counter")

_ARABIC_REMINDER_TYPES = ("arabic_review_reminder", "arabic_review_escalation")


def count_arabic_reminders(neon_url: str, user_id: str, hours: int = 24) -> int:
    """Count Arabic reminder messages sent to user_id in the last `hours` hours.

    Returns an int — the number of arabic_review_reminder / arabic_review_escalation
    rows in message_log within the window. This is a proxy for consecutive ignored
    cycles: each fired reminder that wasn't followed by cards done counts as one skip.

    Returns 0 on any DB error (fail-safe: no escalation rather than false escalation).
    """
    import psycopg2  # lazy import: not installed in CI without Neon
    cutoff = datetime.now() - timedelta(hours=hours)
    try:
        with psycopg2.connect(neon_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM message_log"
                    " WHERE type = ANY(%s) AND user_id = %s AND sent_at >= %s",
                    (list(_ARABIC_REMINDER_TYPES), user_id, cutoff),
                )
                row = cur.fetchone()
                return int(row[0]) if row else 0
    except Exception as e:
        logger.error(f"arabic_skip_counter: DB query failed: {e}")
        return 0
