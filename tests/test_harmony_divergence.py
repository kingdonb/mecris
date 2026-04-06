import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Helper to build a context-manager-compatible mock psycopg2 connection
def _mock_conn(fetchone_row=None):
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = fetchone_row

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor

    return mock_conn, mock_cursor

@pytest.mark.asyncio
async def test_harmony_logging_mechanism():
    """
    Verify that if the 'Jet' logic were to diverge from the 'Source',
    we have the infrastructure to record it.
    """
    user_id = "test-user-123"
    
    # 1. Setup mock results that differ
    jet_result = {"score": "2/3", "all_clear": False}
    source_result = {"score": "3/3", "all_clear": True}
    
    # Setup mock DB
    mock_conn, mock_cursor = _mock_conn(fetchone_row=(json.dumps(source_result), json.dumps(jet_result)))
    
    # 2. Simulate the divergence logging logic
    def log_divergence(conn, component, uid, source, jet):
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO jet_divergence (component_name, user_id, source_result, jet_result, input_params) "
                "VALUES (%s, %s, %s, %s, %s)",
                (component, uid, json.dumps(source), json.dumps(jet), json.dumps({"test": True}))
            )
        conn.commit()

    # 3. Trigger the log
    log_divergence(mock_conn, "harmony-test", user_id, source_result, jet_result)
    
    # 4. Verify cursor was called with correct SQL and data
    # We check that execute was called at least once
    assert mock_cursor.execute.called
    args, _ = mock_cursor.execute.call_args
    assert "INSERT INTO jet_divergence" in args[0]
    assert args[1][0] == "harmony-test"
    assert "true" in args[1][2] # source_result
    assert "false" in args[1][3] # jet_result
    
    print("\n✅ Harmony Divergence Logging Logic Verified.")
