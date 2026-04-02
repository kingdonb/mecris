"""
ghost.presence — Cooperative lock for autonomous Mecris ghost sessions.

A ghost session is an autonomous agent run (bot or cron) that must yield
to a human operator if one is actively using the workspace. This module
provides two layers of presence coordination:

1. **File-based lock** (original API, unchanged): A ``presence.lock`` file
   used as a lightweight local signal. All existing callers continue to work.

2. **Neon-backed presence store** (Phase 1 — kingdonb/mecris#164): A
   ``presence`` table in the shared Neon database enabling globally-visible
   coordination between distributed agents. Introduces the POUND_SAND /
   SHITS_ON_FIRE_YO (SOFY) cooperative state machine.

File-based usage (unchanged)::

    from ghost.presence import acquire_lock, release_lock, check_presence

    status = check_presence()
    if status.human_present:
        print(f"Human detected ({status.age_seconds:.0f}s ago). Yielding.")
        sys.exit(1)

    with acquire_lock() as lock:
        # do ghost work
        ...

Neon-backed usage::

    from ghost.presence import get_neon_store, StatusType

    store = get_neon_store()          # None if NEON_DB_URL not set
    if store:
        store.upsert(user_id, StatusType.PULSE)
        store.set_pound_sand(user_id)  # human says "back off"
        store.escalate_to_sofy(user_id)  # bot emergency override
"""

import os
import time
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import Optional

try:
    import psycopg2
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    psycopg2 = None
    _PSYCOPG2_AVAILABLE = False


# ─── File-based presence lock (original API, unchanged) ──────────────────────

# Age threshold: locks younger than this are considered "active" human presence.
PRESENCE_TTL_SECONDS = 30 * 60  # 30 minutes

DEFAULT_LOCK_PATH = os.path.join(os.getcwd(), "presence.lock")


@dataclass
class PresenceStatus:
    """Result of a presence check."""
    lock_exists: bool
    human_present: bool  # True if lock is fresh (within TTL)
    age_seconds: Optional[float]  # None if no lock file
    lock_path: str


def _lock_path(path: Optional[str] = None) -> str:
    return path or DEFAULT_LOCK_PATH


def check_presence(lock_path: Optional[str] = None, ttl: int = PRESENCE_TTL_SECONDS) -> PresenceStatus:
    """
    Check whether a human presence lock exists and is still fresh.

    Returns a PresenceStatus with `human_present=True` if the lock file
    exists and is younger than `ttl` seconds.
    """
    path = _lock_path(lock_path)
    if not os.path.exists(path):
        return PresenceStatus(lock_exists=False, human_present=False, age_seconds=None, lock_path=path)

    age = time.time() - os.path.getmtime(path)
    human_present = age < ttl
    return PresenceStatus(lock_exists=True, human_present=human_present, age_seconds=age, lock_path=path)


def acquire_lock(lock_path: Optional[str] = None) -> str:
    """
    Write the presence lock file, recording the current Unix timestamp.

    Returns the path of the lock file created.
    """
    path = _lock_path(lock_path)
    with open(path, "w") as f:
        f.write(str(int(time.time())))
    return path


def release_lock(lock_path: Optional[str] = None) -> bool:
    """
    Remove the presence lock file if it exists.

    Returns True if a lock was removed, False if there was nothing to remove.
    """
    path = _lock_path(lock_path)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


@contextmanager
def presence_lock(lock_path: Optional[str] = None):
    """
    Context manager that acquires the presence lock on entry and releases it
    on exit (even if an exception is raised).

    Example::

        with presence_lock("/tmp/mecris.lock"):
            do_ghost_work()
    """
    path = acquire_lock(lock_path)
    try:
        yield path
    finally:
        release_lock(path)


# ─── Neon-backed presence store (Phase 1 — kingdonb/mecris#164) ──────────────

class StatusType(Enum):
    """Presence/attention state stored in the Neon ``presence`` table."""
    PULSE = "pulse"
    ACTIVE_HUMAN = "active_human"
    NEEDS_ATTENTION = "needs_attention"
    POUND_SAND = "pound_sand"
    SHITS_ON_FIRE_YO = "shits_on_fire_yo"


@dataclass
class PresenceRecord:
    """A row from the Neon ``presence`` table."""
    user_id: str
    last_active: datetime
    source: str
    status_type: StatusType


_UPSERT_SQL = """
    INSERT INTO presence (user_id, last_active, source, status_type)
    VALUES (%s, NOW() AT TIME ZONE 'UTC', %s, %s)
    ON CONFLICT (user_id) DO UPDATE
        SET last_active  = NOW() AT TIME ZONE 'UTC',
            source       = EXCLUDED.source,
            status_type  = EXCLUDED.status_type
    RETURNING user_id, last_active, source, status_type
"""

_GET_SQL = """
    SELECT user_id, last_active, source, status_type
    FROM presence
    WHERE user_id = %s
"""


class NeonPresenceStore:
    """Read/write the Neon-backed presence table.

    All writes are upserts — one row per user_id.  Callers never need to
    manage INSERT vs UPDATE themselves.
    """

    def __init__(self, neon_url: str):
        self.neon_url = neon_url

    def _row_to_record(self, row) -> PresenceRecord:
        user_id, last_active, source, status_type_str = row
        return PresenceRecord(
            user_id=user_id,
            last_active=last_active,
            source=source,
            status_type=StatusType(status_type_str),
        )

    def upsert(self, user_id: str, status_type: StatusType, source: str = "cli") -> PresenceRecord:
        """Upsert a presence record. Creates or overwrites the row for user_id."""
        with psycopg2.connect(self.neon_url) as conn:
            with conn.cursor() as cur:
                cur.execute(_UPSERT_SQL, (user_id, source, status_type.value))
                row = cur.fetchone()
        return self._row_to_record(row)

    def get(self, user_id: str) -> Optional[PresenceRecord]:
        """Return the current presence record for user_id, or None if absent."""
        with psycopg2.connect(self.neon_url) as conn:
            with conn.cursor() as cur:
                cur.execute(_GET_SQL, (user_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def set_pound_sand(self, user_id: str, source: str = "cli") -> PresenceRecord:
        """Human-triggered: deny bot attention. Signals bot to back off."""
        return self.upsert(user_id, StatusType.POUND_SAND, source)

    def escalate_to_sofy(self, user_id: str, source: str = "bot") -> PresenceRecord:
        """Bot emergency override. Sets SOFY regardless of current status.

        SOFY (SHITS_ON_FIRE_YO) overrides even POUND_SAND — use only for
        critical system failures or high-risk derailments that require
        immediate human attention.
        """
        return self.upsert(user_id, StatusType.SHITS_ON_FIRE_YO, source)


def get_neon_store(neon_url: Optional[str] = None) -> Optional[NeonPresenceStore]:
    """Return a NeonPresenceStore if psycopg2 and a DB URL are available.

    Falls back gracefully: returns None when psycopg2 is not installed or
    when no URL is provided and NEON_DB_URL is not set. Callers should
    treat None as "Neon unavailable, use file-based lock instead."
    """
    if not _PSYCOPG2_AVAILABLE:
        return None
    url = neon_url or os.getenv("NEON_DB_URL")
    if not url:
        return None
    return NeonPresenceStore(url)
