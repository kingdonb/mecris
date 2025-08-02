# Beeminder Activity Tracking Integration

## Current State - First Deliverable

### Goal Discovery ✅
- **Found target goal**: `bike` - "Distance biked" 
- **Current progress**: 1108.95 miles (target: 999.71)
- **Status**: SAFE with 811-day buffer
- **Rate**: 2.07 miles/week

### API Limitation Discovered 🔍
The current Beeminder MCP endpoints don't provide "last datapoint timestamp" information:
- `/beeminder/status` - shows current values, safety buffers, deadlines
- `/beeminder/emergency` - urgent goals only  
- `/beeminder/alert` - SMS for emergencies

**Cannot determine**: Whether activity was logged today from existing API responses.

## Proposed Solution - Daily Activity Tracker

### Concept
Since we're pinging Beeminder multiple times daily via `/narrator/context`, we can:

1. **Track daily deltas** - Compare current_value changes between API calls
2. **Log activity detection** - Record when values increase 
3. **Build reminder system** - Alert if no activity detected by afternoon

### Implementation Strategy

```python
# New tracking table/file
daily_activity_log = {
    "2025-08-02": {
        "bike": {
            "morning_value": 1108.95,
            "evening_value": 1110.23,  # +1.28 miles detected
            "activity_detected": True,
            "last_check": "2025-08-02T16:30:00"
        }
    }
}
```

### Reminder Logic
```python
def check_afternoon_activity():
    if hour >= 14 and not today_activity_detected("bike"):
        send_sms("🚶‍♂️ Time for a walk! Your bike goal needs you (and so does your dog)")
```

### Next Steps
1. Add daily value tracking to MCP server
2. Create afternoon reminder endpoint  
3. Integrate with existing Twilio alert system
4. Test with real walk/bike logging

## Walking Goal Context
- Goal slug: `bike` (but tracks any miles - walking, biking, etc.)
- User logs all walking/biking miles here
- Dog needs walks = priority reminder trigger
- Afternoon timing preferred for nudges

---
*Generated during Beeminder MCP exploration - 2025-08-02*