import logging
from datetime import datetime, time, timezone
from ghost.presence import PresenceRecord, get_neon_store, StatusType

logger = logging.getLogger("mecris.ghost")

# Configuration for Ghost Archivist
SILENCE_THRESHOLD_SECONDS = 12 * 3600  # 12 hours
NIGHT_WINDOW_START = 22                # 10 PM
NIGHT_WINDOW_END = 23                  # 11:59 PM
GHOST_COOLDOWN_SECONDS = 12 * 3600     # 12 hours

def should_ghost_wake_up(record: PresenceRecord, current_time: datetime) -> bool:
    """
    Returns True if the ghost should perform an archival sync.
    """
    # 1. Silence Check: Is the human actually gone?
    if record.last_human_activity:
        silence_duration = (current_time - record.last_human_activity).total_seconds()
        if silence_duration < SILENCE_THRESHOLD_SECONDS:
            return False
            
    # 2. Night Window Check: Is it the right time of day?
    if not (NIGHT_WINDOW_START <= current_time.hour <= NIGHT_WINDOW_END):
        return False
        
    # 3. Ghost Activity De-duplication: Did we already do this today?
    if record.last_ghost_activity:
        ghost_silence = (current_time - record.last_ghost_activity).total_seconds()
        if ghost_silence < GHOST_COOLDOWN_SECONDS:
            return False
            
    return True

async def perform_archival_sync(user_id: str):
    """
    Stub for the actual archival sync actions (trigger_language_sync, upload_walk, etc).
    """
    # In a real implementation, this would import and call the tools.
    # For now, we update the ghost activity timestamp.
    store = get_neon_store()
    if store:
        store.upsert(user_id, StatusType.ACTIVE_GHOST, source="archivist")

async def archivists_round_robin():
    """
    Iterates through all users and performs archival sync if needed.
    """
    store = get_neon_store()
    if not store:
        logger.warning("Archivist: Neon store unavailable.")
        return
        
    try:
        user_ids = store.get_all_users()
    except Exception as e:
        logger.error(f"Archivist: Failed to fetch users: {e}")
        return

    current_time = datetime.now(timezone.utc)
    
    for user_id in user_ids:
        try:
            record = store.get(user_id)
            if record and should_ghost_wake_up(record, current_time):
                logger.info(f"Archivist: Waking up for user {user_id}")
                await perform_archival_sync(user_id)
        except Exception as e:
            logger.error(f"Archivist: Failed processing user {user_id}: {e}")
