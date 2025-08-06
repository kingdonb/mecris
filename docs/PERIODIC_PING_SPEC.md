# Periodic Ping System Specification

> Autonomous operation system for scheduled Mecris narrator check-ins

## Overview

The periodic ping system enables Claude to autonomously contribute to goal tracking and accountability between active user sessions. This system provides scheduled "drops in the bucket" that maintain momentum on longer-term objectives.

## Core Concept

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Cron Job      │───►│  HTTP Ping       │───►│  Claude Code    │
│   (scheduled)   │    │  /narrator/ping  │    │  (autonomous)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ▼
                       ┌──────────────┐         ┌──────────────┐
                       │   Mecris     │         │  Session Log │
                       │   Context    │         │  + Actions   │
                       └──────────────┘         └──────────────┘
```

## Implementation Components

### 1. Ping Endpoint

```python
@app.post("/narrator/ping")
async def narrator_ping(background_tasks: BackgroundTasks):
    """
    Periodic autonomous check-in endpoint for Claude narrator
    Triggers strategic assessment and action recommendations
    """
    context = await get_narrator_context()
    
    # Determine if immediate action needed
    critical_items = []
    
    # Check beemergencies
    emergencies = await beeminder_client.get_emergencies()
    critical_emergencies = [e for e in emergencies if e["urgency"] == "IMMEDIATE"]
    
    if critical_emergencies:
        critical_items.extend([f"🚨 BEEMERGENCY: {e['goal_slug']}" for e in critical_emergencies])
        # Send immediate alert
        background_tasks.add_task(send_emergency_alert, critical_emergencies)
    
    # Check stale todos (>7 days without update)
    stale_todos = await obsidian_client.get_stale_todos(days=7)
    if len(stale_todos) > 5:
        critical_items.append(f"📝 {len(stale_todos)} stale todos need review")
    
    # Log ping activity
    ping_summary = {
        "timestamp": datetime.now().isoformat(),
        "critical_items": critical_items,
        "goals_status": context["goals_status"],
        "recommendations": context["recommendations"],
        "next_ping": (datetime.now() + timedelta(hours=4)).isoformat()
    }
    
    await obsidian_client.log_ping_activity(ping_summary)
    
    return {
        "ping_processed": True,
        "critical_items_found": len(critical_items),
        "action_taken": len(critical_items) > 0,
        "next_ping_scheduled": ping_summary["next_ping"]
    }
```

### 2. Cron Job Configuration

**Basic Ping Schedule** (4-hour intervals during work hours):
```bash
# Mecris periodic pings - every 4 hours, 9am-9pm
0 9,13,17,21 * * * curl -X POST http://localhost:8000/narrator/ping
```

**Enhanced Schedule** (context-aware timing):
```bash
# Morning briefing - daily at 8am
0 8 * * * curl -X POST http://localhost:8000/narrator/morning-briefing

# Work session pings - every 3 hours during work time
0 9,12,15,18 * * 1-5 curl -X POST http://localhost:8000/narrator/ping

# Evening wrap-up - daily at 8pm
0 20 * * * curl -X POST http://localhost:8000/narrator/evening-summary

# Weekend check-in - Saturday at 10am
0 10 * * 6 curl -X POST http://localhost:8000/narrator/weekend-check
```

### 3. Autonomous Decision Making

The ping system follows these decision rules:

#### Immediate Action Required
- **Beemergencies** (safebuf ≤ 0): Send SMS alert immediately
- **Critical deadlines** (<24 hours): Log urgent reminder
- **System failures** (MCP disconnections): Alert user

#### Strategic Assessment
- **Goal drift detection**: No progress in >3 days
- **Todo backlog growth**: >15 pending items
- **Pattern recognition**: Repeated missed deadlines

#### Background Maintenance
- **Session log cleanup**: Archive old entries
- **Data validation**: Check for formatting issues
- **Health monitoring**: Service connectivity checks

### 4. Ping Types and Responses

#### 4.1 Standard Ping
```json
{
  "type": "standard_ping",
  "assessment": {
    "beeminder_status": "2 goals at risk",
    "todo_backlog": 8,
    "recent_activity": "3 goals updated today"
  },
  "recommendations": [
    "Focus on 'writing' goal - derails in 2 days",
    "Clear 3 quick todos to reduce backlog"
  ],
  "next_action": "monitor"
}
```

#### 4.2 Emergency Ping Response
```json
{
  "type": "emergency_ping",
  "critical_issues": [
    {
      "goal": "daily-words",
      "status": "DERAILING_NOW",
      "action": "SMS_SENT",
      "message": "🚨 daily-words goal needs immediate data!"
    }
  ],
  "escalation": "sms_alert_sent",
  "next_action": "monitor_closely"
}
```

#### 4.3 Morning Briefing
```json
{
  "type": "morning_briefing",
  "daily_focus": [
    "Complete KubeCon abstract draft",
    "Address 2 Beeminder goals at risk"
  ],
  "schedule_conflicts": [],
  "prep_needed": "Review yesterday's session notes",
  "motivation": "💪 3 successful days in a row - maintain momentum!"
}
```

### 5. Integration with User Sessions

When user starts an active Claude Code session:

1. **Context Handoff**: Recent ping logs provide session context
2. **Priority Queue**: Critical items from pings become immediate focus
3. **Progress Tracking**: User actions resolve ping-identified issues
4. **Feedback Loop**: Session outcomes inform future ping logic

### 6. Configuration and Tuning

#### Environment Variables
```env
# Ping system configuration
PING_ENABLED=true
PING_FREQUENCY_HOURS=4
PING_WORK_HOURS_START=9
PING_WORK_HOURS_END=21
EMERGENCY_SMS_ENABLED=true
PING_LOG_RETENTION_DAYS=30
```

#### Adaptive Scheduling
- **High activity periods**: More frequent pings
- **Vacation mode**: Reduced ping frequency
- **Crisis mode**: Continuous monitoring for critical goals

### 7. Success Metrics

- **Response Time**: How quickly beemergencies are addressed
- **Goal Compliance**: Reduction in derailments after ping alerts
- **User Satisfaction**: Perceived value of autonomous assistance
- **System Reliability**: Uptime and accurate assessments

## Implementation Phases

### Phase 1: Basic Ping Endpoint ✅
- Standard ping endpoint with context gathering
- Simple cron job integration
- Basic logging

### Phase 2: Emergency Detection 🚧
- Beemergency classification and SMS alerts
- Critical item identification
- Escalation logic

### Phase 3: Strategic Assessment 🔄
- Pattern recognition in goal behavior
- Adaptive recommendations
- Context-aware scheduling

### Phase 4: Learning System 🔮
- User preference learning
- Effectiveness measurement
- Self-improving ping logic

---

This autonomous ping system transforms Claude from a reactive assistant into a proactive cognitive partner, maintaining continuous awareness of your goals and providing strategic intervention when needed.