import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
from ghost.presence import PresenceRecord, StatusType
from ghost.archivist_logic import archivists_round_robin

@pytest.mark.asyncio
async def test_round_robin_triggers_sync_for_silent_user():
    # Setup mocks
    mock_store = MagicMock()
    # User 1: Silent, needs sync
    last_human = datetime(2026, 4, 4, 8, 0, 0, tzinfo=timezone.utc)
    current_time = datetime(2026, 4, 4, 22, 30, 0, tzinfo=timezone.utc)
    
    record = PresenceRecord(
        user_id="user1",
        last_active=last_human,
        last_human_activity=last_human,
        last_ghost_activity=None,
        source="cli",
        status_type=StatusType.ACTIVE_HUMAN
    )
    
    mock_store.get_all_users.return_value = ["user1"]
    mock_store.get.return_value = record
    
    mock_sync = AsyncMock()
    
    with patch("ghost.archivist_logic.get_neon_store", return_value=mock_store):
        with patch("ghost.archivist_logic.datetime") as mock_datetime:
            mock_datetime.now.return_value = current_time
            mock_datetime.timezone = timezone
            
            # We mock the actual sync actions
            with patch("ghost.archivist_logic.perform_archival_sync", mock_sync):
                await archivists_round_robin()
                
    # Verify sync was called
    mock_sync.assert_called_once_with("user1")

@pytest.mark.asyncio
async def test_round_robin_skips_active_user():
    # Setup mocks
    mock_store = MagicMock()
    # User 1: Active human
    current_time = datetime(2026, 4, 4, 22, 30, 0, tzinfo=timezone.utc)
    
    record = PresenceRecord(
        user_id="user1",
        last_active=current_time,
        last_human_activity=current_time,
        last_ghost_activity=None,
        source="cli",
        status_type=StatusType.ACTIVE_HUMAN
    )
    
    mock_store.get_all_users.return_value = ["user1"]
    mock_store.get.return_value = record
    
    mock_sync = AsyncMock()
    
    with patch("ghost.archivist_logic.get_neon_store", return_value=mock_store):
        with patch("ghost.archivist_logic.datetime") as mock_datetime:
            mock_datetime.now.return_value = current_time
            
            with patch("ghost.archivist_logic.perform_archival_sync", mock_sync):
                await archivists_round_robin()
                
    # Verify sync was NOT called
    mock_sync.assert_not_called()
