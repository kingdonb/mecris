import pytest
import os
import json
import base64
import time
from unittest.mock import patch, MagicMock
from services.encryption_service import EncryptionService
from beeminder_client import BeeminderClient
from scripts.clozemaster_scraper import ClozemasterScraper
from services.neon_sync_checker import NeonSyncChecker

def test_encryption_service_roundtrip():
    key = "0" * 64 # 32-byte zero key in hex
    svc = EncryptionService(key_hex=key)
    plaintext = "super-secret-token-123"
    
    encrypted = svc.encrypt(plaintext)
    assert encrypted != plaintext
    assert len(encrypted) > 24 # nonce(12) + tag(16) + data
    
    decrypted = svc.decrypt(encrypted)
    assert decrypted == plaintext

@pytest.mark.asyncio
@patch("psycopg2.connect")
async def test_beeminder_client_loads_encrypted_creds(mock_connect):
    key = "0" * 64
    svc = EncryptionService(key_hex=key)
    enc_user = svc.encrypt("testuser")
    enc_token = svc.encrypt("secret-token")

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Return (beeminder_user_encrypted, beeminder_token_encrypted, beeminder_user)
    mock_cur.fetchone.return_value = (enc_user, enc_token, None)
    
    with patch.dict(os.environ, {"MASTER_ENCRYPTION_KEY": key, "NEON_DB_URL": "postgres://fake"}):
        client = BeeminderClient(user_id="user-123")
        await client._load_credentials()
        
    assert client.username == "testuser"
    assert client.auth_token == "secret-token"

@pytest.mark.asyncio
@patch("psycopg2.connect")
async def test_clozemaster_scraper_loads_encrypted_creds(mock_connect):
    key = "0" * 64
    svc = EncryptionService(key_hex=key)
    enc_email = svc.encrypt("user@example.com")
    enc_pass = svc.encrypt("password123")
    
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    mock_cur.fetchone.return_value = (enc_email, enc_pass)
    
    with patch.dict(os.environ, {"MASTER_ENCRYPTION_KEY": key, "NEON_DB_URL": "postgres://fake"}):
        scraper = ClozemasterScraper(user_id="user-456")
        await scraper._load_credentials()
        
    assert scraper.email == "user@example.com"
    assert scraper.password == "password123"

# Dummy JWT for testing (unverified decoding)
def create_dummy_jwt(sub, exp=None):
    if exp is None:
        exp = int(time.time()) + 3600
    
    header = {"alg": "RS256", "typ": "JWT", "kid": "test-kid"}
    payload = {
        "sub": sub,
        "exp": exp,
        "iss": "https://metnoom.urmanac.com",
        "aud": "mecris-go"
    }
    
    def b64_encode(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().replace('=', '')
    
    return f"{b64_encode(header)}.{b64_encode(payload)}.dummy-signature"

@pytest.fixture
def neon_checker():
    with patch.dict(os.environ, {"NEON_DB_URL": "postgres://user:pass@localhost/db", "DEFAULT_USER_ID": "default-user"}):
        return NeonSyncChecker()

def test_neon_sync_checker_initialization(neon_checker):
    assert neon_checker.db_url == "postgres://user:pass@localhost/db"
    # default_user_id was removed when credentials_manager replaced DEFAULT_USER_ID env-var lookup


@patch("psycopg2.connect")
def test_has_walk_today_with_user_id(mock_connect, neon_checker):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = (1,)

    user_id = "test-user-123"
    with patch.object(neon_checker, 'resolve_user_id', return_value=user_id):
        result = neon_checker.has_walk_today(user_id=user_id)

    assert result is True
    # Verify user_id was used in query
    args, kwargs = mock_cur.execute.call_args
    assert "AND user_id = %s" in args[0]
    assert user_id in args[1]

@patch("psycopg2.connect")
def test_get_language_stats_with_user_id(mock_connect, neon_checker):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchall.return_value = [
        ("ARABIC", 10, 5, 50, 1.5, 120, "reviewstack", 3),
        ("GREEK", 20, 10, 100, 2.0, 240, "greek", 1)
    ]
    user_id = "test-user-456"
    with patch.object(neon_checker, 'resolve_user_id', return_value=user_id):
        stats = neon_checker.get_language_stats(user_id=user_id)

    assert "arabic" in stats
    assert stats["arabic"]["multiplier"] == 1.5
    assert "greek" in stats

    # Verify user_id was used in query
    args, kwargs = mock_cur.execute.call_args
    assert "WHERE user_id = %s" in args[0]
    assert user_id in args[1]

@patch("psycopg2.connect")
def test_update_pump_multiplier_with_user_id(mock_connect, neon_checker):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cur

    user_id = "test-user-789"
    with patch.object(neon_checker, 'resolve_user_id', return_value=user_id):
        success = neon_checker.update_pump_multiplier("ARABIC", 3.0, user_id=user_id)

    assert success is True
    # Verify user_id was used in query
    args, kwargs = mock_cur.execute.call_args
    assert "AND user_id = %s" in args[0]
    assert user_id in args[1]
    assert 3.0 in args[1]

@patch("psycopg2.connect")
def test_get_latest_walk_with_user_id(mock_connect, neon_checker):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = (time.time(), 1000, 800.0, "google_fit")

    user_id = "test-user-walk"
    with patch.object(neon_checker, 'resolve_user_id', return_value=user_id):
        walk = neon_checker.get_latest_walk(user_id=user_id)

    assert walk["step_count"] == 1000
    # Verify user_id was used in query
    args, kwargs = mock_cur.execute.call_args
    assert "WHERE user_id = %s" in args[0]
    assert user_id in args[1]
