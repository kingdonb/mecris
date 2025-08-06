# 🛠️ Mecris Services Guide

> "No more 'run this? run that?' — your complete service operations manual"

## Quick Start Commands

```bash
# Start the complete Mecris system
export SKIP_HEALTH_PROMPT=true && source venv/bin/activate && python start_server.py &

# Check if services are running
curl -s http://localhost:8000/health | jq .

# Get your complete narrator context (the main endpoint Claude uses)
curl -s http://localhost:8000/narrator/context | jq .

# Stop all services
pkill -f "python start_server.py"
```

## Service Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        MECRIS SYSTEM                            │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI MCP Server (localhost:8000)                           │
│  ├─ /narrator/context  ← Main Claude endpoint                  │
│  ├─ /budget/status     ← Budget monitoring                     │
│  ├─ /beeminder/*       ← Goal tracking                         │
│  ├─ /goals             ← Obsidian goals (if configured)        │
│  └─ /health            ← Service status                        │
└─────────────────────────────────────────────────────────────────┘
```

## Core Services Status

### ✅ Operational Services
- **FastAPI MCP Server**: Core API running on port 8000
- **Beeminder Integration**: Goal tracking and derailment detection
- **Claude Budget Monitor**: Real-time credit usage tracking
- **Twilio SMS**: Alert system (needs credential setup)

### ⚠️ Degraded Services  
- **Obsidian MCP**: Vault integration unreachable (needs separate MCP server)
- **Twilio Authentication**: SMS alerts disabled (needs proper credentials)

## Essential Endpoints

### `/narrator/context` - The Big Picture
**What Claude needs to be your cognitive agent**
```bash
curl -s http://localhost:8000/narrator/context
```
Returns:
- Budget status and days remaining
- Beeminder goal emergencies
- Strategic recommendations
- Urgent action items

### `/budget/status` - Financial Reality Check
```bash
curl -s http://localhost:8000/budget/status
```
Current status: ⚠️ WARNING (1.1 days left, $0.98 remaining)

### `/beeminder/status` - Goal Portfolio
```bash
curl -s http://localhost:8000/beeminder/status
```
Shows all 10 Beeminder goals with derailment risk levels.

### `/health` - System Status
```bash
curl -s http://localhost:8000/health
```
Service-by-service health check for debugging.

## Environment Setup

### Required Environment Variables
```bash
# Beeminder (✅ Working)
BEEMINDER_USERNAME=yebyenw
BEEMINDER_AUTH_TOKEN=85iSj2uB9dQskyc8G8ji

# Twilio (⚠️ Needs Setup)
TWILIO_ACCOUNT_SID=your_account_sid  # Currently placeholder
TWILIO_AUTH_TOKEN=your_auth_token    # Currently placeholder
TWILIO_FROM_NUMBER=+1234567890       # Your Twilio number

# Obsidian (⚠️ Needs MCP Server)
OBSIDIAN_VAULT_PATH=/path/to/vault

# Server Config
SKIP_HEALTH_PROMPT=true  # Essential for background startup
PORT=8000
DEBUG=false
```

### Setting Up Missing Services

#### Fix Twilio SMS Alerts
1. Get real Twilio credentials from twilio.com
2. Update environment variables
3. Restart server

#### Fix Obsidian Integration
1. Install Obsidian MCP server separately
2. Configure vault path
3. Update CLAUDE.md with your vault structure

## Operational Workflows

### Morning Startup Routine
```bash
# 1. Start Mecris
export SKIP_HEALTH_PROMPT=true && source venv/bin/activate && python start_server.py &

# 2. Check narrator context
curl -s http://localhost:8000/narrator/context | jq '.summary, .urgent_items, .recommendations'

# 3. Review budget constraints
curl -s http://localhost:8000/budget/status | jq '.days_remaining, .credits_remaining'
```

### Budget Monitoring
```bash
# Current budget status
curl -s http://localhost:8000/budget/status | jq '.status, .days_remaining'

# Track new usage (when Claude burns credits)
curl -X POST http://localhost:8000/budget/track -H "Content-Type: application/json" -d '{"cost": 0.50, "description": "Claude Code session"}'
```

### Emergency Alerts
```bash
# Check for beemergencies
curl -s http://localhost:8000/beeminder/emergency

# Trigger manual alert check
curl -X POST http://localhost:8000/beeminder/alert
curl -X POST http://localhost:8000/budget/alert
```

## Development & Debugging

### Logs
```bash
# Server logs
tail -f mecris.log

# Service startup logs
tail -f mecris_server.log
```

### Testing Changes
```bash
# Restart server after code changes
pkill -f "python start_server.py"
export SKIP_HEALTH_PROMPT=true && source venv/bin/activate && python start_server.py &

# Verify health
curl -s http://localhost:8000/health
```

### Adding New Endpoints
1. Edit `mcp_server.py`
2. Add route function
3. Update response models if needed
4. Test with curl
5. Update this guide

## Current System Limitations

### Known Issues
- **Twilio**: SMS alerts disabled (authentication failed)
- **Obsidian**: Vault integration not connected
- **Budget Tracking**: Manual usage recording only

### Workarounds
- Budget monitoring via API works for current usage
- Beeminder integration fully functional
- Core narrator context provides strategic overview

## Integration with Claude

### How Claude Uses This System
1. **Session Start**: Claude calls `/narrator/context` to understand current state
2. **Decision Making**: Uses budget constraints and urgent items to prioritize
3. **Action Planning**: References beeminder alerts and recommendations
4. **Session Logging**: Can POST session summaries back to system

### Making Claude More Context-Aware
```bash
# Before major work, Claude should check:
curl -s http://localhost:8000/narrator/context | jq '.budget_status.days_remaining, .urgent_items'

# Result influences:
# - Scope of work (budget constraints)  
# - Priority (urgent beemergencies)
# - Approach (high-value focus when budget low)
```

## Next Improvements

### High Priority
1. Fix Twilio credentials for real SMS alerts
2. Connect Obsidian MCP for vault integration  
3. Automate budget usage tracking

### Medium Priority
1. Add time tracker integration
2. Implement periodic ping system
3. Enhanced alert logic

### Low Priority  
1. Web dashboard for monitoring
2. Slack integration
3. Advanced goal correlation analysis

---

**Status**: Operational with degraded features (1.1 days budget remaining)  
**Last Updated**: 2025-08-01  
**Next Review**: When budget critically low or major feature added