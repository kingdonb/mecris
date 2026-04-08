"""
Unit tests for BeeminderClient._load_credentials() (yebyen/mecris#123).

Covers the four code paths added in d1d32b5:
1. Encrypted path: both columns present, decrypted via EncryptionService
2. Plaintext fallback: beeminder_user_encrypted is NULL, uses plain beeminder_user
3. Env-var fallback: DB row has no credentials at all, falls back to env vars
4. No-NEON_DB_URL path: skips DB entirely, reads env vars directly
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

from services.encryption_service import EncryptionService

TEST_KEY = "0" * 64  # 32-byte AES-256 key as 64 hex chars


@pytest.fixture
def enc():
    """Real EncryptionService with a known test key."""
    with patch.dict(os.environ, {"MASTER_ENCRYPTION_KEY": TEST_KEY}):
        yield EncryptionService()


def _make_db_mock(row):
    """Return a mock psycopg2 connect that yields the given row from fetchone."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = row
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn


@pytest.mark.asyncio
async def test_load_credentials_encrypted_path(enc):
    """Encrypted columns are decrypted and loaded into client attributes."""
    encrypted_user = enc.encrypt("testuser")
    encrypted_token = enc.encrypt("secret-token")
    # Row: (enc_user, enc_token, plain_user)
    row = (encrypted_user, encrypted_token, None)

    mock_tracker = MagicMock()
    mock_tracker.resolve_user_id.return_value = "test-user-id"

    with patch.dict(os.environ, {"NEON_DB_URL": "postgres://fake", "MASTER_ENCRYPTION_KEY": TEST_KEY}), \
         patch("psycopg2.connect", return_value=_make_db_mock(row)), \
         patch("usage_tracker.UsageTracker", return_value=mock_tracker):

        from beeminder_client import BeeminderClient
        client = BeeminderClient(user_id="test-user-id")
        await client._load_credentials()

    assert client.username == "testuser"
    assert client.auth_token == "secret-token"


@pytest.mark.asyncio
async def test_load_credentials_plaintext_fallback(enc):
    """Falls back to plain beeminder_user column when encrypted col is NULL."""
    encrypted_token = enc.encrypt("secret-token")
    # Row: enc_user=NULL, enc_token present, plain_user present
    row = (None, encrypted_token, "plaintext-user")

    mock_tracker = MagicMock()
    mock_tracker.resolve_user_id.return_value = "test-user-id"

    with patch.dict(os.environ, {"NEON_DB_URL": "postgres://fake", "MASTER_ENCRYPTION_KEY": TEST_KEY}), \
         patch("psycopg2.connect", return_value=_make_db_mock(row)), \
         patch("usage_tracker.UsageTracker", return_value=mock_tracker):

        from beeminder_client import BeeminderClient
        client = BeeminderClient(user_id="test-user-id")
        await client._load_credentials()

    assert client.username == "plaintext-user"
    assert client.auth_token == "secret-token"


@pytest.mark.asyncio
async def test_load_credentials_env_var_fallback():
    """When DB row has no credentials, falls back to BEEMINDER_USERNAME/AUTH_TOKEN env vars."""
    row = (None, None, None)  # nothing in DB

    mock_tracker = MagicMock()
    mock_tracker.resolve_user_id.return_value = "test-user-id"

    with patch.dict(os.environ, {
        "NEON_DB_URL": "postgres://fake",
        "BEEMINDER_USERNAME": "env-user",
        "BEEMINDER_AUTH_TOKEN": "env-token",
    }), \
         patch("psycopg2.connect", return_value=_make_db_mock(row)), \
         patch("usage_tracker.UsageTracker", return_value=mock_tracker):

        from beeminder_client import BeeminderClient
        client = BeeminderClient(user_id="test-user-id")
        await client._load_credentials()

    assert client.username == "env-user"
    assert client.auth_token == "env-token"


@pytest.mark.asyncio
async def test_load_credentials_no_neon_db_url():
    """When NEON_DB_URL is absent, _load_credentials uses env vars directly.

    UsageTracker is mocked because it also requires NEON_DB_URL — the no-DB
    branch in _load_credentials() is reached only after the tracker is
    instantiated, so we stub it out here.
    """
    mock_tracker = MagicMock()
    mock_tracker.resolve_user_id.return_value = "test-user-id"

    # Build env without NEON_DB_URL but with legacy Beeminder env vars
    env = {k: v for k, v in os.environ.items() if k != "NEON_DB_URL"}
    env["BEEMINDER_USERNAME"] = "legacy-user"
    env["BEEMINDER_AUTH_TOKEN"] = "legacy-token"

    with patch.dict(os.environ, env, clear=True), \
         patch("usage_tracker.UsageTracker", return_value=mock_tracker):

        from beeminder_client import BeeminderClient
        client = BeeminderClient()
        await client._load_credentials()

    assert client.username == "legacy-user"
    assert client.auth_token == "legacy-token"
