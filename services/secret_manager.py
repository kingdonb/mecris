"""
services.secret_manager — JIT credential retrieval for subprocess env injection.

Fetches named secrets from os.environ (the primary source) and returns only
the requested keys, never the full environment. This prevents credential
leakage when spawning headless subprocesses.

Future extension: if NEON_DB_URL is available and a key is absent from the
environment, a Neon-backed secure-variable lookup can be added here without
changing any call sites.

Usage::

    from services.secret_manager import SecretManager, HEADLESS_LOOPBACK_KEYS

    sm = SecretManager()
    env = sm.get_secrets(HEADLESS_LOOPBACK_KEYS)
    # env is a shallow dict — safe to pass as subprocess env
"""

import logging
import os
from typing import List

logger = logging.getLogger("mecris.services.secret_manager")

# Keys that the gemini --yolo subprocess needs to authenticate with the LLM API.
HEADLESS_LOOPBACK_KEYS: List[str] = ["GEMINI_API_KEY"]


class SecretManager:
    """Retrieves named secrets from the environment for subprocess injection.

    Fetches only the requested keys from ``os.environ``, never modifying it.
    Missing keys are logged at DEBUG level and omitted from the result so
    callers can decide whether to fail-closed or proceed with degraded keys.
    """

    def get_secrets(self, keys: List[str]) -> dict:
        """Return ``{key: value}`` for each requested key found in ``os.environ``.

        Keys absent from the environment are omitted (not set to ``None``).
        The returned dict is a new object — modifying it does not affect
        ``os.environ``.

        Args:
            keys: Names of environment variables to retrieve.

        Returns:
            Dict containing only the keys that were present in the environment.
        """
        result: dict = {}
        for key in keys:
            val = os.environ.get(key)
            if val is not None:
                result[key] = val
            else:
                logger.debug("SecretManager: key not found in environment: %s", key)
        return result


# Module-level singleton — importers may use this or instantiate their own.
secret_manager = SecretManager()
