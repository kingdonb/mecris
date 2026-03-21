# INTELLIGENT_REMINDER_SYSTEM.md

**Adaptive Daily Reminder System with Graceful Budget Degradation**  
*Specification - 2025-08-04*

## 🎯 VISION

**Core Principle**: Walk reminders work regardless of Claude API budget. Everything else is enhancement.

The system has full access to MCP context (Beeminder, budget, walk status) without Claude credits. The budget only affects message intelligence and decision sophistication:

1. **Enhanced Mode** (Claude available): Intelligent message crafting and complex decision-making
2. **Standard Mode** (Claude constrained): Template-based messages using full MCP context
3. **Base Mode** (Claude exhausted): Simple walk reminders still work perfectly

## 🏗️ SYSTEM ARCHITECTURE

### Multi-Tenant Context Collection

```
Cron → MCP Narrator Context (user_id) → Budget Check → Message Strategy → Delivery
  ↓           ↓                             ↓              ↓            ↓
Hourly    User-Scoped                  Claude credits?   How smart?   Always works
Check     Full State                   (Per User)       (Adaptive)   (Reliable)
```

**Key Insight**: All data (walk status, Beeminder alerts, budget warnings) is scoped by `user_id` in the Neon DB, allowing the system to serve multiple users independently.

### Three-Tier Messaging System

#### Tier 1: Claude-Enhanced (Budget Available)
**When**: Claude credits available for sophisticated analysis
**Capability**: Complex multi-issue prioritization, calendar-aware timing, personalized tone
```python
# Claude gets full context + instructions for nuanced decisions
claude_prompt = f"""
Context: {narrator_context}
Time: {current_time}
Instructions: {claude_md_content}

Analyze this context and decide if/what to message. Consider:
- Work day vs personal time appropriateness
- Message timing and user likely availability  
- Priority of walk vs other urgent items
- Tone that motivates without annoying
"""
```
#### Tier 2: Smart Templates (Budget Constrained)
**When**: Claude credits too low for regular use, but some available for emergencies
**Capability**: Full MCP context analysis with deterministic template selection
```python
def smart_template_decision(context, current_time, user_id):
    """All MCP data available - just using templates instead of Claude"""
    walk_needed = context["daily_walk_status"]["status"] == "needed"
    urgent_beeminder = [alert for alert in context["beeminder_alerts"] if "CRITICAL" in alert]
    budget_critical = any("BUDGET CRITICAL" in item for item in context["urgent_items"])
    hour = current_time.hour

    # Primary: Walk reminders (afternoon window: 1 PM - 5 PM)
    if walk_needed and 13 <= hour <= 17:
        return select_walk_template(context, hour, user_id)
...
```
    # Secondary: Morning beeminder summary (once per day, non-work-interrupting)
    if urgent_beeminder and hour in [8, 9] and not sent_today("beeminder_summary"):
        return f"🚨 FYI: {len(urgent_beeminder)} Beeminder goals need attention today"
    
    # Tertiary: Budget warnings (work hours OK since it affects work)
    if budget_critical and 9 <= hour <= 17:
        return template_budget_warning(context)
    
    return None
```

#### Tier 3: Base Mode (Budget Exhausted)  
**When**: No Claude credits available
**Capability**: Walk reminders only, using MCP context for basic personalization
```python
def base_mode_decision(context, current_time):
    """Minimal but reliable - walk reminders work no matter what"""
    walk_needed = context["daily_walk_status"]["status"] == "needed"
    hour = current_time.hour
    
    if walk_needed and 14 <= hour <= 17:
        return random.choice([
            "🚶‍♂️ Walk reminder - dogs are waiting!",
            "🐕 Time for that daily walk",
            "🚶‍♂️ No walk logged yet today - time to move!"
        ])
    
    return None  # Only walk reminders in base mode
```

## 🧠 CONTEXT USAGE BY TIER

### What We Get From MCP (No Claude Credits Needed)
```json
{
  "daily_walk_status": {"status": "needed", "message": "🚶‍♂️ No walk detected today"},
  "beeminder_alerts": ["arabiya: Derails in 2 days", "coding: Due today"],
  "urgent_items": ["BUDGET CRITICAL: 0.0 days left"],
  "budget_status": {"remaining_budget": 0.50, "days_remaining": 0},
  "goal_runway": [...]
}
```

### How Each Tier Uses This Data

**Tier 1 (Claude Enhanced)**:
- Analyzes full context for subtle timing decisions
- Considers work/personal time appropriateness  
- Crafts personalized, contextual messages
- Makes complex priority decisions between competing needs

**Tier 2 (Smart Templates)**:
- Uses all MCP data for template selection logic
- Applies work-day filtering for Beeminder alerts
- Provides rich context in templates ("bike goal needs 0.5 miles")
- Handles multiple alerts intelligently

**Tier 3 (Base Mode)**:
- Only processes walk status from MCP context
- Ignores everything else to stay simple and reliable
- Always works even if MCP server has partial failures

## 🕐 WORK/PERSONAL TIME AWARENESS

### Beeminder Alert Scheduling
**Philosophy**: Personal goals shouldn't interrupt work flow

```python
def is_appropriate_for_beeminder_alert(current_time, alert_type):
    hour = current_time.hour
    weekday = current_time.weekday()  # 0=Monday
    
    # Walk reminders: Always OK (affects health + work productivity)
    if alert_type == "walk":
        return True
    
    # Other Beeminder: Morning briefing or evening wrap-up
    if alert_type == "beeminder_summary":
        return hour in [8, 9] or hour in [18, 19, 20]
    
    # Critical emergencies: OK during work hours but limit frequency
    if alert_type == "beeminder_critical":
        return not sent_today("beeminder_critical")
    
    return False
```

### Future: Calendar Integration
**Nice-to-have**: Morning walk reminders if afternoon calendar is packed
```python
def should_send_morning_walk_alert(context, calendar_events):
    """
    If we know afternoon is busy, remind in morning
    But only when Claude budget allows the sophistication
    """
    afternoon_busy = has_meetings_between(calendar_events, 14, 17)
    walk_needed = context["daily_walk_status"]["status"] == "needed"
    morning_hours = 8 <= datetime.now().hour <= 11
    
    return walk_needed and afternoon_busy and morning_hours
```

## 🔧 IMPLEMENTATION STATUS

### Phase 1: Multi-Tenancy & Reliability (Complete)
**Goal**: User-isolated reminders work with $0 Claude budget

- [x] user_id scoping for all database tables
- [x] Walk reminder window (1 PM - 5 PM)
- [x] Known-working template selection (`mecris_status_v2`)
- [x] `/intelligent-reminder/trigger` endpoint with user_id support
- [x] Shared message log to prevent multi-user spam

### Phase 2: Smart Templates (Next)
**Goal**: Rich context without Claude costs

- [ ] Template system using full MCP context  
- [ ] Work/personal time filtering
- [ ] Multi-issue template selection
- [ ] Beeminder summary messages (morning/evening)

### Phase 3: Claude Enhancement (Future)
**Goal**: Sophisticated decision-making when budget allows

- [ ] Claude API integration for Tier 1
- [ ] Contextual message crafting
- [ ] Calendar integration for timing
- [ ] Learning from user behavior

## 📱 MESSAGE EXAMPLES BY SCENARIO

### Walk Reminders (All Tiers)

**Tier 3 (Base)**:
```
"🚶‍♂️ Walk reminder - dogs are waiting!"
```

**Tier 2 (Smart Template - mecris_status_v2)**:
```
"Mecris Status Update: Your goal Daily Walk is currently NOT FOUND. Your commitment Boris & Fiona is EXPECTANT. Time: 01:58 PM."
```

**Tier 1 (Claude Enhanced)**:
```
"🚶‍♂️ Perfect timing for a walk! I see your next meeting isn't until 4 PM, the bike goal needs progress, and honestly you could probably use the mental break before tackling that arabiya goal that's getting close."
```

### Beeminder Alerts (Tier 2+)

**Tier 2 Morning Summary**:
```
"🚨 FYI: 2 Beeminder goals need attention today - arabiya (2 days) and coding (due tonight)"
```

**Tier 1 Contextual**:
```
"🚨 Heads up: arabiya derails in 2 days, but since it's Wednesday morning, focus on work goals first. Handle the Arabic practice tonight when you're winding down."
```

### Budget Warnings (All Tiers)

**Tier 2 Template**:
```
"💰 Budget alert: $0.50 remaining. Focus mode activated."
```

**Tier 1 Strategic**:
```
"💰 Down to $0.50 - time to wrap up the high-value work. That arabiya goal can wait, but finish documenting the walk reminder system first."
```

## 🎯 SUCCESS CRITERIA

### Phase 1 Success
- [ ] Walk reminders sent daily at 2-5 PM if no activity logged
- [ ] System works with $0.00 Claude budget
- [ ] No spam (max 1 walk reminder per day)
- [ ] Cron job reliable and error-resistant

### Full System Success  
- [ ] Appropriate work/personal time boundaries respected
- [ ] Rich context utilized without requiring Claude credits
- [ ] Claude enhancement adds genuine value when available
- [ ] User actually walks more consistently

## 🔗 DEPENDENCIES & INTEGRATION

### Requires (Already Built)
- `BEEMINDER_ACTIVITY_TRACKING.md` - Walk detection
- `TWILIO_SETUP_GUIDE.md` - Message delivery
- MCP narrator context endpoints

### Extends
- Budget tier assessment functions
- Template selection logic
- Work/personal time filtering

### Future Integrations
- Calendar APIs for meeting awareness
- Weather APIs for walk appropriateness
- Success tracking (did user walk after reminder?)

---

## 🎭 DESIGN PHILOSOPHY

**"Walk Reminders Always Work, Everything Else is Bonus"**

The system is architected so that the core accountability function (dog walking) never depends on external resources. Claude budget affects message quality and decision sophistication, but basic functionality remains bulletproof.

When we hit budget exhaustion in ~2 days, the walk reminders will continue working, providing real-world validation of the graceful degradation approach.

*The best reminder system is the one that still works when everything else fails.*