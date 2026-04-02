"""
ghost.presence — Cooperative lock for autonomous Mecris ghost sessions.

A ghost session is an autonomous agent run (bot or cron) that must yield
to a human operator if one is actively using the workspace. This module
provides a file-based presence lock so sessions can signal liveness and
defer to each other without stomping state.

Usage::

    from ghost.presence import acquire_lock, release_lock, check_presence

    status = check_presence()
    if status.human_present:
        print(f"Human detected ({status.age_seconds:.0f}s ago). Yielding.")
        sys.exit(1)

    with acquire_lock() as lock:
        # do ghost work
        ...  # lock is auto-released on context exit
"""

import os
import time
from dataclasses import dataclass
from contextlib import contextmanager
from typing import Optional


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
