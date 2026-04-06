import pytest
from unittest.mock import patch, MagicMock
from services.encryption_service import EncryptionService
import os

@pytest.fixture
def encryption_service():
    # Ensure a key is present for testing
    with patch.dict(os.environ, {"MASTER_ENCRYPTION_KEY": "0" * 64}):
        return EncryptionService()

def test_encryption_service_roundtrip(encryption_service):
    """Happy path: encryption and decryption work correctly."""
    original_text = "Sunkworks secret 123"
    ciphertext = encryption_service.encrypt(original_text)
    
    assert ciphertext != original_text
    assert len(ciphertext) > len(original_text)
    
    decrypted = encryption_service.decrypt(ciphertext)
    assert decrypted == original_text

@pytest.mark.asyncio
async def test_encryption_regression_message_log_content():
    """Verify message_log.content encryption in mcp_server logic."""
    from mcp_server import send_reminder_message
    from datetime import datetime
    
    test_msg = "Ultra secret PII content"
    message_data = {"message": test_msg, "to_number": "+1234567890"}
    
    # We mock psycopg2 to inspect the SQL executed
    with patch("psycopg2.connect") as mock_connect, \
         patch("mcp_server.usage_tracker") as mock_tracker, \
         patch("mcp_server.smart_send_message", return_value={"sent": True}):
        
        # Setup mock tracker with encryption active
        enc = EncryptionService()
        with patch.dict(os.environ, {"MASTER_ENCRYPTION_KEY": "0" * 64}):
             mock_tracker.encryption = EncryptionService()
        
        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_cur = mock_conn.cursor.return_value.__enter__.return_value
        
        await send_reminder_message(message_data, user_id="test-user")
        
        # Verify that the executed SQL for INSERT contained ciphertext, not plaintext
        # cur.execute("INSERT INTO message_log ... (..., content) VALUES (..., %s)", (...))
        # The content is the 7th parameter in the query we saw in mcp_server.py
        
        # Find the execute call for message_log
        log_call = None
        for call in mock_cur.execute.call_args_list:
            if "INSERT INTO message_log" in call[0][0]:
                log_call = call
                break
        
        assert log_call is not None
        sql_params = log_call[0][1]
        
        # The params are (today, msg_type, now, target_user_id, status_val, error_val, encrypted_content)
        # encrypted_content is index 6
        captured_content = sql_params[6]
        
        assert captured_content != test_msg
        # Decrypt it back to verify it was indeed our message
        decrypted = mock_tracker.encryption.decrypt(captured_content)
        assert decrypted == test_msg

@pytest.mark.asyncio
async def test_encryption_regression_walk_gps_points():
    """Verify walk_inferences.gps_route_points encryption in mcp_server logic."""
    from mcp_server import upload_walk
    
    test_points = "[{'lat': 1.23, 'lon': 4.56}]"
    walk_data = {
        "start_time": "2026-04-05T12:00:00",
        "end_time": "2026-04-05T13:00:00",
        "step_count": 5000,
        "distance_meters": 3500,
        "distance_source": "gps",
        "gps_route_points": test_points
    }
    
    with patch("psycopg2.connect") as mock_connect, \
         patch("mcp_server.usage_tracker") as mock_tracker:
        
        # Setup mock tracker with encryption active
        with patch.dict(os.environ, {"MASTER_ENCRYPTION_KEY": "0" * 64}):
             mock_tracker.encryption = EncryptionService()
        
        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_cur = mock_conn.cursor.return_value.__enter__.return_value
        
        await upload_walk(walk_data, user_id="test-user")
        
        # Verify that the executed SQL for INSERT contained ciphertext
        log_call = None
        for call in mock_cur.execute.call_args_list:
            if "INSERT INTO walk_inferences" in call[0][0]:
                log_call = call
                break
        
        assert log_call is not None
        sql_params = log_call[0][1]
        
        # The params are (user_id, start_time, end_time, step_count, distance_meters, distance_source, confidence_score, gps_points, 'logging')
        # gps_points is index 7
        captured_points = sql_params[7]
        
        assert captured_points != test_points
        decrypted = mock_tracker.encryption.decrypt(captured_points)
        assert decrypted == test_points

@pytest.mark.asyncio
async def test_encryption_regression_autonomous_turns():
    """Verify autonomous_turns.summary/outcome encryption."""
    from usage_tracker import UsageTracker
    
    test_summary = "Ghost did some secret work"
    test_outcome = "success - result hidden"
    
    with patch("psycopg2.connect") as mock_connect:
        # We need a real UsageTracker but with mocked DB
        with patch.dict(os.environ, {"MASTER_ENCRYPTION_KEY": "0" * 64, "NEON_DB_URL": "postgres://fake"}):
            tracker = UsageTracker()
            tracker.use_neon = True
            
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_cur = mock_conn.cursor.return_value.__enter__.return_value
            
            tracker.record_autonomous_turn(
                agent_type="ghost",
                agenda_slug="archivist",
                input_tokens=100,
                output_tokens=200,
                cost=0.01,
                summary=test_summary,
                outcome=test_outcome,
                user_id="test-user"
            )
            
            # Verify that the executed SQL for INSERT contained ciphertext
            log_call = None
            for call in mock_cur.execute.call_args_list:
                if "INSERT INTO autonomous_turns" in call[0][0]:
                    log_call = call
                    break
            
            assert log_call is not None
            sql_params = log_call[0][1]
            
            # The params are (now, agent_type, agenda_slug, input_tokens, output_tokens, cost, stored_summary, stored_outcome, container_id, target_user_id)
            # stored_summary is index 6, stored_outcome is index 7
            captured_summary = sql_params[6]
            captured_outcome = sql_params[7]
            
            assert captured_summary != test_summary
            assert captured_outcome != test_outcome
            
            assert tracker.encryption.decrypt(captured_summary) == test_summary
            assert tracker.encryption.decrypt(captured_outcome) == test_outcome
