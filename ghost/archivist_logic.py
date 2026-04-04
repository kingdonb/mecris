from datetime import datetime, time
from ghost.presence import PresenceRecord

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
