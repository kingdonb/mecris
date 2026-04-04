from datetime import datetime, time
from ghost.presence import PresenceRecord

def should_ghost_wake_up(record: PresenceRecord, current_time: datetime) -> bool:
    """
    Returns True if the ghost should perform an archival sync.
    Criteria:
    1. Human has been silent for > 12 hours.
    2. Current time is between 10 PM and 11:59 PM (22:00 - 23:59).
    3. Ghost hasn't already performed a sync in the last 12 hours.
    """
    # 1. Silence Check
    if record.last_human_activity:
        silence_duration = current_time - record.last_human_activity
        if silence_duration.total_seconds() < 12 * 3600:
            return False
            
    # 2. Night Window Check (22:00 - 23:59)
    # We use .time() which is naive, or match against specific hours
    if not (22 <= current_time.hour <= 23):
        return False
        
    # 3. Ghost Activity De-duplication
    if record.last_ghost_activity:
        ghost_silence = current_time - record.last_ghost_activity
        if ghost_silence.total_seconds() < 12 * 3600:
            return False
            
    return True
