"""
Token Bank — Autonomous Agent Rate-Limiting for Mecris.

Tracks daily token allowances per user and records autonomous turn metadata
in Neon. Guards against runaway agent loops exhausting the monthly API budget.

Plan: yebyen/mecris#254 / kingdonb/mecris#209
"""
import os
import logging
from datetime import datetime, timezone, date
from typing import Optional

import psycopg2
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("mecris.services.token_bank")


class TokenBudgetExceededError(Exception):
    """Raised when an agent turn is rejected because the daily allowance is used up."""


class TokenBankService:
    """
    Checks and debits token allowances before autonomous agent turns.

    Uses two Neon tables:
    - ``token_bank``: per-user daily allowance and rolling usage counter.
    - ``autonomous_turns``: per-turn audit log (start, end, exit_code, tokens).

    All public methods are synchronous and accept a ``db_url`` override for
    testing; production code reads ``NEON_DB_URL`` from the environment.
    """

    DEFAULT_DAILY_ALLOWANCE = 50_000

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv("NEON_DB_URL")
        if not self.db_url:
            logger.warning("NEON_DB_URL not configured. Token bank checks will be skipped.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_and_debit(self, user_id: str, tokens_requested: int, agent_role: str) -> int:
        """
        Verify the user has enough daily allowance, then debit it.

        Returns the updated ``tokens_used_today`` value on success.
        Raises ``TokenBudgetExceededError`` if the allowance is exhausted.

        If ``NEON_DB_URL`` is not set, silently allows the turn (fail-open for
        offline/test environments that do not configure a real DB).
        """
        if not self.db_url:
            logger.warning("No DB URL — skipping token bank check for %s", user_id)
            return 0

        with psycopg2.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                self._ensure_row(cur, user_id)
                self._reset_if_new_day(cur, user_id)

                cur.execute(
                    "SELECT daily_allowance, tokens_used_today FROM token_bank WHERE user_id = %s FOR UPDATE",
                    (user_id,),
                )
                row = cur.fetchone()
                daily_allowance, tokens_used_today = row

                if tokens_used_today + tokens_requested > daily_allowance:
                    raise TokenBudgetExceededError(
                        f"Agent '{agent_role}' rejected: {user_id} has used "
                        f"{tokens_used_today}/{daily_allowance} tokens today; "
                        f"requested {tokens_requested} more."
                    )

                cur.execute(
                    "UPDATE token_bank SET tokens_used_today = tokens_used_today + %s WHERE user_id = %s "
                    "RETURNING tokens_used_today",
                    (tokens_requested, user_id),
                )
                new_total = cur.fetchone()[0]
                conn.commit()
                logger.info(
                    "Debited %d tokens for '%s' (%s). Daily total: %d/%d.",
                    tokens_requested, agent_role, user_id, new_total, daily_allowance,
                )
                return new_total

    def record_turn_start(self, user_id: str, agent_role: str) -> Optional[int]:
        """
        Insert an ``autonomous_turns`` row for a new agent turn.

        Returns the ``turn_id`` so the caller can update it with
        ``record_turn_end`` after the turn completes.
        """
        if not self.db_url:
            return None

        with psycopg2.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO autonomous_turns (user_id, agent_role, start_time)
                    VALUES (%s, %s, NOW())
                    RETURNING turn_id
                    """,
                    (user_id, agent_role),
                )
                turn_id = cur.fetchone()[0]
                conn.commit()
                return turn_id

    def record_turn_end(
        self,
        turn_id: int,
        exit_code: int,
        tokens_consumed: int,
        summary: Optional[str] = None,
    ) -> None:
        """Update an existing ``autonomous_turns`` row when the turn finishes."""
        if not self.db_url:
            return

        with psycopg2.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE autonomous_turns
                    SET end_time = NOW(), exit_code = %s, tokens_consumed = %s, summary = %s
                    WHERE turn_id = %s
                    """,
                    (exit_code, tokens_consumed, summary, turn_id),
                )
                conn.commit()

    def get_failed_turns(self, user_id: str, limit: int = 10):
        """
        Return the most recent failed turns (exit_code != 0) for a user.

        Used by the Post-Mortem Generator (kingdonb/mecris#216).
        """
        if not self.db_url:
            return []

        with psycopg2.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT turn_id, agent_role, start_time, end_time, exit_code, tokens_consumed, summary
                    FROM autonomous_turns
                    WHERE user_id = %s AND exit_code != 0
                    ORDER BY start_time DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                rows = cur.fetchall()
                return [
                    {
                        "turn_id": r[0],
                        "agent_role": r[1],
                        "start_time": r[2],
                        "end_time": r[3],
                        "exit_code": r[4],
                        "tokens_consumed": r[5],
                        "summary": r[6],
                    }
                    for r in rows
                ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_row(self, cur, user_id: str) -> None:
        """Insert a default token_bank row if none exists yet."""
        cur.execute(
            """
            INSERT INTO token_bank (user_id, daily_allowance, tokens_used_today, last_reset_date)
            VALUES (%s, %s, 0, CURRENT_DATE)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id, self.DEFAULT_DAILY_ALLOWANCE),
        )

    def _reset_if_new_day(self, cur, user_id: str) -> None:
        """Zero out tokens_used_today if last_reset_date is before today."""
        cur.execute(
            """
            UPDATE token_bank
            SET tokens_used_today = 0, last_reset_date = CURRENT_DATE
            WHERE user_id = %s AND last_reset_date < CURRENT_DATE
            """,
            (user_id,),
        )
