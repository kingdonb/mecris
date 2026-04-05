import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
from ghost.presence import PresenceRecord, StatusType
from ghost.archivist_logic import archivists_round_robin

@pytest.mark.asyncio
async def test_round_robin_triggers_sync_for_unsynced_user():
    # Setup mocks
    mock_store = MagicMock()
    current_time = datetime(2026, 4, 4, 22, 30, 0, tzinfo=timezone.utc)
    
    # User 1: Never synced by ghost
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
            mock_datetime.timezone = timezone
            
            # We mock the actual sync actions
            with patch("ghost.archivist_logic.perform_archival_sync", mock_sync):
                await archivists_round_robin()
                
    # Verify sync was called
    mock_sync.assert_called_once_with("user1")

@pytest.mark.asyncio
async def test_round_robin_skips_recently_synced_user():
    # Setup mocks
    mock_store = MagicMock()
    current_time = datetime(2026, 4, 4, 22, 30, 0, tzinfo=timezone.utc)
    
    # User 1: Synced 1 hour ago
    last_ghost = current_time - timedelta(hours=1)
    
    record = PresenceRecord(
        user_id="user1",
        last_active=last_ghost,
        last_human_activity=None,
        last_ghost_activity=last_ghost,
        source="archivist",
        status_type=StatusType.ACTIVE_GHOST
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
