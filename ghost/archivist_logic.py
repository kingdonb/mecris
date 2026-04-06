import logging
import zoneinfo
import asyncio
from datetime import datetime, time, timezone
from ghost.presence import PresenceRecord, get_neon_store, StatusType

logger = logging.getLogger("mecris.ghost")

# Configuration for Ghost Archivist
GHOST_COOLDOWN_SECONDS = 12 * 3600     # 12 hours
HUMAN_SILENCE_THRESHOLD_SECONDS = 3600  # 1 hour
ARCHIVIST_HOUR_START = 2               # 2 AM UTC
ARCHIVIST_HOUR_END = 5                 # 5 AM UTC

def should_ghost_wake_up(record: PresenceRecord, current_time: datetime) -> bool:
    """
    Returns True if the ghost should perform an archival sync.
    Heuristic:
    1. Idempotency: Must be at least 12 hours since last ghost activity.
    2. Quiet Window: Do not wake up if a human was active in the last hour.
    """
    # 1. Ghost Activity De-duplication (Idempotency)
    if record.last_ghost_activity:
        ghost_silence = (current_time - record.last_ghost_activity).total_seconds()
        if ghost_silence < GHOST_COOLDOWN_SECONDS:
            return False
            
    # 2. Human Presence Cooperative Silence
    if record.last_human_activity:
        human_silence = (current_time - record.last_human_activity).total_seconds()
        if human_silence < HUMAN_SILENCE_THRESHOLD_SECONDS:
            return False

    return True

async def perform_archival_sync(user_id: str):
    """
    Performs archival sync actions:
    1. Language sync (Clozemaster -> Beeminder).
    2. Physical activity sync (Push 0.0 if no activity to prevent derailment).
    3. Update presence status in Neon.
    """
    from services.language_sync_service import LanguageSyncService
    from beeminder_client import BeeminderClient
    
    logger.info(f"Archivist: Performing archival sync for user {user_id}")
    beeminder_client = BeeminderClient(user_id=user_id)
    
    # 1. Language Sync
    try:
        lang_service = LanguageSyncService(beeminder_client)
        sync_result = await lang_service.sync_all(user_id=user_id)
        if sync_result.get("success"):
            logger.info(f"Archivist: Language sync completed for {user_id}")
        else:
            logger.warning(f"Archivist: Language sync reported failure for {user_id}: {sync_result.get('error')}")
    except Exception as e:
        logger.error(f"Archivist: Language sync failed for {user_id}: {e}")

    # 2. Physical Activity Sync (The "Ghost Heartbeat")
    # We no longer push 0.0 to odometer goals (like 'bike') to prevent derailment.
    # Reality Enforcement: If the user didn't walk, they derail.
    try:
        activity_status = await beeminder_client.get_daily_activity_status("bike")
        if not activity_status.get("has_activity_today"):
            logger.info(f"Archivist: No activity today for 'bike' for {user_id}. Reality Enforcement: No safety datapoint pushed.")
        else:
            logger.info(f"Archivist: Activity already detected for 'bike' goal for {user_id}.")
    except Exception as e:
        logger.error(f"Archivist: Physical activity sync check failed for {user_id}: {e}")

    # 3. Update Presence
    store = get_neon_store()
    if store:
        try:
            store.upsert(user_id, StatusType.ACTIVE_GHOST, source="archivist")
            logger.info(f"Archivist: Presence updated to ACTIVE_GHOST for {user_id}")
        except Exception as e:
            logger.error(f"Archivist: Failed to update presence for {user_id}: {e}")

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
