# Mecris MCP Endpoints Documentation

> "Welcome to Mecris, the not-a-Torment-Nexus you were warned about. This isn't dystopia, it's **delegation**."

## Overview

Mecris exposes 10 MCP (Model Context Protocol) endpoints that provide Claude with real-time access to your accountability systems, budget tracking, and goal management. This documentation covers each endpoint's functionality and integration confidence.

## Endpoint Specifications

### 🎯 Core Context & Strategy

#### `get_narrator_context`
**Confidence: 9/10** ⭐⭐⭐⭐⭐⭐⭐⭐⭐

- **Purpose**: Primary strategic overview endpoint that aggregates all data sources
- **Returns**: Unified context with goals, budget, Beeminder alerts, and AI-generated recommendations  
- **Current Status**: 5 active goals, 9 Beeminder goals, 41 days budget remaining, $22.37 left
- **Integration**: Fully operational - combines local database, Beeminder API, and budget tracking
- **Why 9/10**: Extremely comprehensive and clearly working, minor uncertainty on Obsidian integration fallbacks

---

### 📊 Beeminder Integration

#### `get_beeminder_status` 
**Confidence: 10/10** ⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐

- **Purpose**: Portfolio view of all Beeminder goals with risk assessment
- **Returns**: 9 goals with detailed status, risk levels, deadlines, and pledge amounts
- **Current Status**: 1 CAUTION (ellinika - 3 days to derail), 8 SAFE goals
- **Integration**: Direct Beeminder API integration with 30-minute caching
- **Why 10/10**: Perfect data returned, clearly connected to live Beeminder API

#### `send_beeminder_alert`
**Confidence: 8/10** ⭐⭐⭐⭐⭐⭐⭐⭐

- **Purpose**: Checks for critical emergencies and sends SMS alerts via Twilio
- **Returns**: Alert status and emergency count
- **Current Status**: No critical emergencies found
- **Integration**: Beeminder API + Twilio SMS + cooldown logic
- **Why 8/10**: Logic works, but SMS delivery untested in this session

#### `get_daily_activity`
**Confidence: 9/10** ⭐⭐⭐⭐⭐⭐⭐⭐⭐

- **Purpose**: Checks if daily activity logged for specific Beeminder goal (defaults to "bike")
- **Returns**: Activity status with caching info and user-friendly messages
- **Current Status**: No walk detected today for bike goal
- **Integration**: Beeminder API with 1-hour caching for API rate limiting
- **Why 9/10**: Working perfectly with smart caching, minor uncertainty on edge cases

---

### 💰 Budget & Usage Tracking

#### `get_budget_status`
**Confidence: 10/10** ⭐⭐⭐⭐⭐⭐⭐⭐⭐⭐

- **Purpose**: Current Claude usage budget status with burn rate analysis
- **Returns**: Total/remaining budget, days left, daily burn rate, health status
- **Current Status**: $22.37 remaining of $24.96, 41 days until Sept 30, GOOD health
- **Integration**: Local SQLite database with detailed usage tracking
- **Why 10/10**: Comprehensive budget data, clearly functional local tracking system

#### `record_usage_session`
**Confidence: 9/10** ⭐⭐⭐⭐⭐⭐⭐⭐⭐

- **Purpose**: Logs Claude token usage with cost calculations for budget tracking
- **Parameters**: `input_tokens`, `output_tokens`, `model`, `session_type`, `notes`
- **Integration**: Token cost calculation + SQLite logging
- **Why 9/10**: Well-structured logging system, slight uncertainty on cost accuracy

#### `update_budget`
**Confidence: 8/10** ⭐⭐⭐⭐⭐⭐⭐⭐

- **Purpose**: Manually adjust budget parameters (remaining, total, period_end)
- **Parameters**: `remaining_budget` (required), `total_budget`, `period_end`  
- **Integration**: Direct database updates with validation
- **Why 8/10**: Function exists and structured properly, but manual update reliability depends on user input

---

### 🎯 Goal & Task Management

#### `add_goal`
**Confidence: 7/10** ⭐⭐⭐⭐⭐⭐⭐

- **Purpose**: Creates new goals in local database
- **Parameters**: `title` (required), `description`, `priority` (high/medium/low), `due_date`
- **Integration**: Local SQLite database with goal management
- **Why 7/10**: Standard CRUD operation, but untested in this session

#### `complete_goal`
**Confidence: 7/10** ⭐⭐⭐⭐⭐⭐⭐

- **Purpose**: Marks goals as completed by goal_id
- **Parameters**: `goal_id` (required)
- **Integration**: Local database updates
- **Why 7/10**: Standard database operation, but functionality not verified in testing

---

### 🔔 Smart Reminders

#### `trigger_reminder_check`
**Confidence: 8/10** ⭐⭐⭐⭐⭐⭐⭐⭐

- **Purpose**: Intelligent reminder system that analyzes context and sends appropriate alerts
- **Returns**: Tiered decision-making (base_mode/smart_template/enhanced) based on budget
- **Current Status**: No reminder triggered (outside 2-5pm walk window)
- **Integration**: Context analysis + SMS/WhatsApp delivery + no-spam protection
- **Why 8/10**: Sophisticated logic working, but delivery methods untested

---

## System Architecture Confidence

### High Confidence (9-10/10)
- **Beeminder Integration**: Live API connections working perfectly
- **Budget Tracking**: Comprehensive local database system
- **Context Aggregation**: Successfully combines multiple data sources

### Medium-High Confidence (7-8/10)  
- **SMS/Alert Systems**: Logic implemented but delivery untested
- **Goal Management**: Standard database operations, likely functional
- **Reminder Intelligence**: Complex decision trees implemented

### Integration Notes
- **Obsidian**: Mentioned in code but appears to have fallbacks when unavailable
- **Twilio SMS**: Configured but not verified in testing
- **Caching**: Smart 30-minute (Beeminder) and 1-hour (daily activity) caches implemented
- **A2P Compliance**: SMS consent management system in place

## Usage Patterns

Based on CLAUDE.md instructions, the system expects:
1. **Budget awareness first** - Check remaining days/budget before major tasks
2. **Daily context checks** - Use `get_narrator_context` for strategic overview  
3. **Goal integration** - Beeminder emergencies should influence all planning
4. **Intelligent alerts** - System will escalate via SMS when needed

## Conclusion

Mecris is a genuinely impressive personal accountability system that bridges multiple data sources into a unified cognitive agent interface. The majority of endpoints show strong evidence of real, functional integrations rather than mock implementations.