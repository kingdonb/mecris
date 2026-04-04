"""
HealthChecker — reads scheduler_election table and returns per-process liveness status.
Implements the Python side of kingdonb/mecris#97 (Unified heartbeat and health visibility).
"""
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("mecris.services.health")

STALE_THRESHOLD_SECONDS = 90


class HealthChecker:
    """
    Queries the scheduler_election table to report liveness for all registered processes
    (Python MCP server, Android client, Spin cloud).  Returns a list of process dicts,
    each with: role, process_id, last_heartbeat (ISO string), is_active (bool).
    """

    def __init__(self):
        self.neon_url = os.getenv("NEON_DB_URL")

    def get_process_statuses(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all rows from scheduler_election for user_id (or global rows where user_id IS NULL).
        Returns a list sorted by role.
        """
        if not self.neon_url:
            return []

        try:
            import psycopg2
            with psycopg2.connect(self.neon_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT role, process_id, heartbeat,
                               heartbeat > NOW() - INTERVAL '90 seconds' AS is_active
                        FROM scheduler_election
                        WHERE user_id = %s OR user_id IS NULL
                        ORDER BY role
                    """, (user_id,))
                    rows = cur.fetchall()

            processes = []
            for role, process_id, heartbeat, is_active in rows:
                processes.append({
                    "role": role,
                    "process_id": process_id,
                    "last_heartbeat": heartbeat.isoformat() if heartbeat else None,
                    "is_active": bool(is_active),
                })
            return processes

        except Exception as e:
            logger.error(f"HealthChecker.get_process_statuses failed: {e}")
            raise

    def get_system_health(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Return a summary health dict suitable for surfacing in get_narrator_context or directly.
        Callers that need scheduler metadata (leader, process_id) should inject it afterwards.
        """
        if not self.neon_url:
            return {"error": "NEON_DB_URL not configured", "processes": []}

        try:
            processes = self.get_process_statuses(user_id)
            any_active = any(p["is_active"] for p in processes)
            return {
                "processes": processes,
                "overall_status": "healthy" if any_active else "degraded",
            }
        except Exception as e:
            return {"error": str(e), "processes": []}
