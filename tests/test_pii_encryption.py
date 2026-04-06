"""
TDG tests for PII encryption in database-backed tables.

Verifies that sensitive fields are stored as ciphertext, not plaintext,
so that direct SQL access does not reveal PII.

Plan issue: yebyen/mecris#94
"""
import sys
import pytest
import os
from unittest.mock import patch, MagicMock, call

from services.encryption_service import EncryptionService

TEST_KEY = "0" * 64  # 32-byte zero key in hex (safe for unit tests)


# ---------------------------------------------------------------------------
# usage_sessions.notes — already encrypted; this is a regression guard
# ---------------------------------------------------------------------------

@patch("psycopg2.connect")
def test_usage_sessions_notes_are_encrypted_at_rest(mock_connect):
    """
    UsageTracker.record_session must encrypt the 'notes' field before
    persisting it. Direct SQL should never see plaintext.
    """
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    # Budget tracking row: COUNT(*) returns 0 so no init insert needed
    mock_cur.fetchone.return_value = (1,)

    with patch.dict(os.environ, {
        "NEON_DB_URL": "postgres://fake",
        "MASTER_ENCRYPTION_KEY": TEST_KEY,
        "DEFAULT_USER_ID": "test-user",
    }):
        from usage_tracker import UsageTracker
        with patch.object(UsageTracker, "init_database"):
            tracker = UsageTracker.__new__(UsageTracker)
            tracker.neon_url = "postgres://fake"
            tracker.user_id = "test-user"
            tracker.use_neon = True
            tracker.encryption = EncryptionService(key_hex=TEST_KEY)
            tracker.pricing = {
                "claude-3-5-sonnet-20241022": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000}
            }

        plaintext_notes = "Session note: user mentioned anxiety about Arabic progress"
        tracker.record_session(
            model="claude-3-5-sonnet-20241022",
            input_tokens=100,
            output_tokens=200,
            notes=plaintext_notes,
            user_id="test-user",
        )

    # Find the INSERT call for usage_sessions
    insert_call = None
    for c in mock_cur.execute.call_args_list:
        sql = c[0][0] if c[0] else ""
        if "INSERT INTO usage_sessions" in sql:
            insert_call = c
            break

    assert insert_call is not None, "No INSERT INTO usage_sessions call found"
    args = insert_call[0][1]  # positional params tuple
    stored_notes = args[6]  # notes is the 7th param (0-indexed: timestamp,model,in,out,cost,type,notes,user_id)

    assert stored_notes != plaintext_notes, (
        f"notes column must NOT be stored as plaintext. Got: {stored_notes!r}"
    )
    # Must be decryptable back to original
    svc = EncryptionService(key_hex=TEST_KEY)
    assert svc.decrypt(stored_notes) == plaintext_notes


# ---------------------------------------------------------------------------
# message_log.error_msg — RED test: currently stored as plaintext
# ---------------------------------------------------------------------------

def test_message_log_error_msg_encryption_implemented_in_mcp_server():
    """
    Code-level assertion: mcp_server.py must encrypt error_val before writing
    it to message_log.error_msg. Twilio error strings can contain phone numbers
    (e.g., '+15550001234') that must not be stored as plaintext.

    RED: fails until mcp_server.py adds the encryption call.
    GREEN: passes once the implementation is in place.
    """
    mcp_server_path = os.path.join(os.path.dirname(__file__), "..", "mcp_server.py")
    with open(mcp_server_path) as f:
        source = f.read()

    # Updated to support try_encrypt() refactor
    assert "encryption.try_encrypt(error_val)" in source or "encryption.encrypt(error_val)" in source, (
        "mcp_server.py must encrypt error_val using usage_tracker.encryption before inserting into message_log."
    )


def test_message_log_error_msg_encryption_roundtrip():
    """
    Verifies the EncryptionService correctly handles error message strings
    (the type that will be encrypted in message_log.error_msg).
    """
    svc = EncryptionService(key_hex=TEST_KEY)
    error_msg = "Failed to send (check twilio_sender logs)"

    encrypted = svc.encrypt(error_msg)
    assert encrypted != error_msg
    assert svc.decrypt(encrypted) == error_msg
