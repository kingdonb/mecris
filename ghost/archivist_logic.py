import logging
import asyncio
from datetime import datetime, timezone
from ghost.presence import PresenceRecord, get_neon_store, StatusType

logger = logging.getLogger("mecris.ghost")

# Configuration for Ghost Archivist
GHOST_COOLDOWN_SECONDS = 12 * 3600     # 12 hours

def should_ghost_wake_up(record: PresenceRecord, current_time: datetime) -> bool:
    """
    Returns True if the ghost should perform an archival sync.

    Continuous reconciliation per the Ghost Archivist spec (SYS-001):
    - Only check idempotency: must be at least 12 hours since last ghost activity.
    - No time-of-day window restriction.
    - No human presence cooperative silence.
    The Ghost is a reality enforcer that runs on a schedule regardless of user activity.
    """
    # Idempotency: do not run if we already synced within the cooldown window.
    if record.last_ghost_activity:
        ghost_silence = (current_time - record.last_ghost_activity).total_seconds()
        if ghost_silence < GHOST_COOLDOWN_SECONDS:
            return False

    return True

async def perform_archival_sync(user_id: str):
    """
    Performs archival sync actions:
    1. Language sync (Clozemaster -> Beeminder). Extrapolates growing backlog if inactive.
    2. Physical activity sync (Log only, Reality Enforcement applies).
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
    # We never push 0.0 to odometer goals (like 'bike').
    # Reality Enforcement: If the user didn't walk, they derail.
    try:
        activity_status = await beeminder_client.get_daily_activity_status("bike")
        if not activity_status.get("has_activity_today"):
            logger.info(f"Archivist: No activity today for 'bike' for {user_id}. Reality Enforcement: User will derail via natural Beeminder extrapolation.")
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
