"""
services.secret_manager — JIT credential retrieval for subprocess env injection.

Fetches named secrets from os.environ (the primary source) and returns only
the requested keys, never the full environment. This prevents credential
leakage when spawning headless subprocesses.

If NEON_DB_URL is set at call time and a key is absent from the environment,
the key is looked up from the ``secure_variables`` table in Neon (psycopg2
required).  The expected table schema is::

    CREATE TABLE IF NOT EXISTS secure_variables (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

This fallback is transparent to callers — no call-site changes are needed.

Usage::

    from services.secret_manager import SecretManager, HEADLESS_LOOPBACK_KEYS

    sm = SecretManager()
    env = sm.get_secrets(HEADLESS_LOOPBACK_KEYS)
    # env is a shallow dict — safe to pass as subprocess env
"""

import logging
import os
from typing import Callable, List, Optional

logger = logging.getLogger("mecris.services.secret_manager")

# Keys that the gemini --yolo subprocess needs to authenticate with the LLM API.
HEADLESS_LOOPBACK_KEYS: List[str] = ["GEMINI_API_KEY"]

_NEON_FALLBACK_SQL = "SELECT value FROM secure_variables WHERE key = %s LIMIT 1"


class SecretManager:
    """Retrieves named secrets from the environment for subprocess injection.

    Fetches only the requested keys from ``os.environ``, never modifying it.
    Missing keys are logged at DEBUG level and omitted from the result so
    callers can decide whether to fail-closed or proceed with degraded keys.

    If *NEON_DB_URL* is present in the environment at call time and a key is
    absent from the environment, the key is looked up from the
    ``secure_variables`` table in Neon.  This fallback is fail-safe: any DB
    error is logged at DEBUG and the key is silently omitted.

    Args:
        _neon_connect: Optional callable used instead of ``psycopg2.connect``
            when performing Neon lookups.  Intended for tests only.
    """

    def __init__(self, _neon_connect: Optional[Callable] = None) -> None:
        self._neon_connect = _neon_connect

    def _fetch_from_neon(
        self, neon_db_url: str, key: str, connect: Callable
    ) -> Optional[str]:
        """Look up *key* from ``secure_variables``. Returns value or ``None``."""
        try:
            with connect(neon_db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(_NEON_FALLBACK_SQL, (key,))
                    row = cur.fetchone()
                    return row[0] if row else None
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "SecretManager: Neon fallback failed for key %s: %s", key, exc
            )
            return None

    def get_secrets(self, keys: List[str]) -> dict:
        """Return ``{key: value}`` for each requested key found in ``os.environ``
        or (when *NEON_DB_URL* is set) in the Neon ``secure_variables`` table.

        Keys absent from all sources are omitted (not set to ``None``).
        The returned dict is a new object — modifying it does not affect
        ``os.environ``.

        Args:
            keys: Names of environment variables / Neon secure-variable keys
                to retrieve.

        Returns:
            Dict containing only the keys that were resolved.
        """
        result: dict = {}
        missing: List[str] = []

        for key in keys:
            val = os.environ.get(key)
            if val is not None:
                result[key] = val
            else:
                logger.debug("SecretManager: key not found in environment: %s", key)
                missing.append(key)

        if missing:
            neon_db_url = os.environ.get("NEON_DB_URL")
            if neon_db_url:
                connect = self._neon_connect
                if connect is None:
                    import psycopg2  # noqa: PLC0415 — lazy import, avoids hard dep at module load

                    connect = psycopg2.connect
                for key in missing:
                    val = self._fetch_from_neon(neon_db_url, key, connect)
                    if val is not None:
                        logger.debug(
                            "SecretManager: key resolved via Neon fallback: %s", key
                        )
                        result[key] = val

        return result


# Module-level singleton — importers may use this or instantiate their own.
secret_manager = SecretManager()
