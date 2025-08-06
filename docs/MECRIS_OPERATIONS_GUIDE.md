# 🛠️ Mecris Operations Guide

> **"Your daily field manual for running a containerized mind palace"**

This is your practical guide to operating Mecris day-to-day. Not theory, not architecture — just the commands, workflows, and procedures you need to keep your cognitive agent system running smoothly.

---

## 🚀 Quick Start (Daily Startup)

### 1. System Health Check
```bash
# Check if MCP server is running
curl -s http://localhost:8000/health || echo "Server down"

# Verify core integrations
curl -s http://localhost:8000/beeminder/status
curl -s http://localhost:8000/narrator/context | head -20
```

### 2. Start/Restart Mecris
```bash
# Full system startup
python start_server.py

# Or manual startup (if start_server.py doesn't exist yet)
python -m uvicorn mcp_server:app --reload --port 8000

# Background startup (for persistent operation)
nohup python -m uvicorn mcp_server:app --port 8000 > mecris_server.log 2>&1 &
```

### 3. Verify Your Context
```bash
# Get full narrator context (what Claude sees)
curl -s http://localhost:8000/narrator/context

# Check budget status
curl -s http://localhost:8000/usage

# Emergency check (any goals derailing?)
curl -s http://localhost:8000/beeminder | grep -i "emergency\|derail"
```

---

## 📋 Daily Operational Workflows

### Morning Ritual (5 minutes)
```bash
# 1. System status
curl -s http://localhost:8000/narrator/context | grep -A5 "Budget\|Emergency\|Goals"

# 2. Today's priorities (🚨 VAPORWARE - planned feature)
curl -s http://localhost:8000/daily/$(date +%Y-%m-%d)/priorities

# 3. Check for overnight alerts
tail -20 mecris.log | grep -i "alert\|emergency\|derail"
```

### Midday Check-in (2 minutes)
```bash
# Quick pulse check
curl -s http://localhost:8000/narrator/context | head -10

# Budget burn rate (🚨 VAPORWARE - needs Claude Monitor MCP)
curl -s http://localhost:8000/usage/burn_rate
```

### Evening Wrap-up (10 minutes)
```bash
# 1. Log today's progress (🚨 VAPORWARE - manual for now)
echo "$(date): [your progress summary]" >> mecris.log

# 2. Check tomorrow's risks
curl -s http://localhost:8000/beeminder | grep -B2 -A2 "tomorrow"

# 3. Set autonomous ping schedule (🚨 VAPORWARE - cron integration planned)
# This will eventually auto-schedule tomorrow's check-ins
curl -X POST http://localhost:8000/schedule/tomorrow
```

---

## 🎯 Core Operational Commands

### Context Retrieval
```bash
# Full narrator context (what Claude gets)
curl -s http://localhost:8000/narrator/context

# Specific data sources
curl -s http://localhost:8000/beeminder          # Goal status
curl -s http://localhost:8000/obsidian/goals    # Obsidian goal extraction
curl -s http://localhost:8000/usage             # Budget tracking
curl -s http://localhost:8000/daily/2025-08-01  # Today's notes
```

### System Diagnostics
```bash
# Server health
curl -s http://localhost:8000/health

# Check all integrations
curl -s http://localhost:8000/integrations/status

# View recent session logs
tail -50 mecris.log

# Check for configuration issues
python test_mecris.py --quick-check
```

### Emergency Operations
```bash
# Force beemergency check
curl -s http://localhost:8000/beeminder/check_emergencies

# Send emergency text (🚨 VAPORWARE - requires Twilio config)
curl -X POST http://localhost:8000/alert/sms -d '{"message":"Beemergency detected!"}'

# Trigger immediate Claude session (🚨 VAPORWARE - autonomous agent)
curl -X POST http://localhost:8000/narrator/emergency_session
```

---

## 🚨 Troubleshooting Guide

### Server Won't Start
```bash
# Check if port is in use
lsof -i :8000

# Kill existing process
pkill -f "uvicorn mcp_server"

# Check for missing dependencies
pip install -r requirements.txt

# Start with verbose logging
python -m uvicorn mcp_server:app --log-level debug
```

### Beeminder Integration Issues
```bash
# Test API key
curl -s "https://www.beeminder.com/api/v1/users/me.json?auth_token=YOUR_TOKEN"

# Check local integration
python -c "from beeminder_client import BeeminderClient; print(BeeminderClient().get_goals())"

# Reset Beeminder cache (🚨 VAPORWARE - caching not implemented)
curl -X DELETE http://localhost:8000/cache/beeminder
```

### Obsidian Vault Issues
```bash
# Verify vault path
ls -la "$OBSIDIAN_VAULT_PATH"

# Test file access
python -c "from obsidian_client import ObsidianClient; print(ObsidianClient().get_daily_note('2025-08-01'))"

# Rebuild vault index (🚨 VAPORWARE - indexing planned)
curl -X POST http://localhost:8000/obsidian/reindex
```

### Budget/Usage Tracking Problems
```bash
# Check Claude Monitor connection (🚨 VAPORWARE - needs implementation)
curl -s http://localhost:8000/usage/test_connection

# Manual usage check
python claude_monitor.py --check-balance

# Reset usage tracking (🚨 VAPORWARE)
curl -X POST http://localhost:8000/usage/reset_daily
```

---

## ⚡ Emergency Procedures

### Beemergency Response
1. **Immediate Alert Check**:
   ```bash
   curl -s http://localhost:8000/beeminder | grep -C3 "emergency"
   ```

2. **Get Emergency Details** (🚨 VAPORWARE - enhanced alerts):
   ```bash
   curl -s http://localhost:8000/beeminder/emergency/details
   ```

3. **Send Alert** (🚨 VAPORWARE - Twilio integration):
   ```bash
   python twilio_sender.py "BEEMERGENCY: [goal] derails tomorrow!"
   ```

4. **Trigger Emergency Session** (🚨 VAPORWARE - autonomous Claude):
   ```bash
   curl -X POST http://localhost:8000/narrator/emergency_session \
        -d '{"reason":"beemergency","goal":"[goal_name]"}'
   ```

### Budget Exhaustion Response
1. **Check Remaining Budget**:
   ```bash
   curl -s http://localhost:8000/usage | grep -i "remaining"
   ```

2. **Enable Emergency Mode** (🚨 VAPORWARE - budget-aware operation):
   ```bash
   curl -X POST http://localhost:8000/mode/emergency_budget
   ```

3. **Suspend Non-Critical Operations** (🚨 VAPORWARE):
   ```bash
   curl -X POST http://localhost:8000/suspend/autonomous_pings
   ```

### System Recovery
1. **Full System Reset**:
   ```bash
   pkill -f mecris
   rm -f mecris_server.log
   python start_server.py
   ```

2. **Clear All Caches** (🚨 VAPORWARE):
   ```bash
   curl -X DELETE http://localhost:8000/cache/all
   ```

3. **Verify Core Functions**:
   ```bash
   python test_mecris.py --critical-path-only
   ```

---

## 🔄 Autonomous Operation (The Future)

### Ping Scheduling (🚨 VAPORWARE - cron integration planned)
```bash
# Set up autonomous check-ins
crontab -e
# Add: 0 */4 * * * curl -X POST http://localhost:8000/ping/autonomous

# Manual ping trigger
curl -X POST http://localhost:8000/ping/now

# View ping history
curl -s http://localhost:8000/ping/history
```

### Session Management (🚨 VAPORWARE - persistent Claude sessions)
```bash
# Start persistent narrator session
curl -X POST http://localhost:8000/narrator/start_session

# Send message to active session
curl -X POST http://localhost:8000/narrator/message \
     -d '{"text":"How should I spend the next 2 hours?"}'

# End session and save context
curl -X POST http://localhost:8000/narrator/end_session
```

### Learning System (🚨 VAPORWARE - pattern recognition)
```bash
# View system insights
curl -s http://localhost:8000/insights/patterns

# Export learning data
curl -s http://localhost:8000/insights/export > mecris_insights.json

# Import previous learning
curl -X POST http://localhost:8000/insights/import -d @mecris_insights.json
```

---

## 📊 Monitoring & Maintenance

### Daily Health Checks
```bash
#!/bin/bash
# Save as: daily_health_check.sh

echo "=== Mecris Daily Health Check ==="
echo "Date: $(date)"
echo

echo "1. Server Status:"
curl -s http://localhost:8000/health | head -5

echo -e "\n2. Budget Status:"
curl -s http://localhost:8000/usage | grep -E "(remaining|used|burn_rate)"

echo -e "\n3. Goal Status:"
curl -s http://localhost:8000/beeminder | grep -c "safe\|emergency\|derail"

echo -e "\n4. Recent Alerts:"
tail -5 mecris.log | grep -i "alert\|emergency"

echo -e "\n5. System Uptime:"
ps aux | grep -E "(uvicorn|mcp_server)" | grep -v grep
```

### Weekly Maintenance (🚨 VAPORWARE - automated maintenance)
```bash
# Log rotation
curl -X POST http://localhost:8000/maintenance/rotate_logs

# Performance cleanup
curl -X POST http://localhost:8000/maintenance/cleanup

# Backup session data
curl -s http://localhost:8000/maintenance/backup > mecris_backup_$(date +%Y%m%d).json
```

### Performance Monitoring (🚨 VAPORWARE - metrics collection)
```bash
# Response time check
curl -w "@curl-format.txt" -s http://localhost:8000/narrator/context > /dev/null

# Memory usage
curl -s http://localhost:8000/metrics/memory

# Integration latency
curl -s http://localhost:8000/metrics/integrations
```

---

## 🔧 Configuration Management

### Environment Variables
```bash
# Required
export BEEMINDER_USERNAME="your_username"
export BEEMINDER_AUTH_TOKEN="your_token"

# Optional but recommended
export OBSIDIAN_VAULT_PATH="/path/to/vault"
export TWILIO_ACCOUNT_SID="your_sid"
export TWILIO_AUTH_TOKEN="your_token"
export TWILIO_PHONE_NUMBER="your_number"

# Advanced (🚨 VAPORWARE)
export MECRIS_LOG_LEVEL="INFO"
export MECRIS_CACHE_TTL="300"
export MECRIS_MAX_SESSIONS="5"
```

### Config Validation
```bash
# Test all configurations
python test_mecris.py --config-check

# Test specific integration
python test_mecris.py --test-beeminder
python test_mecris.py --test-obsidian
python test_mecris.py --test-twilio
```

---

## 🎯 Integration Checklist

### After Major Changes
- [ ] Run full test suite: `python test_mecris.py`
- [ ] Verify narrator context: `curl localhost:8000/narrator/context`
- [ ] Check all integrations: `curl localhost:8000/integrations/status`
- [ ] Test emergency procedures: `curl localhost:8000/beeminder/check_emergencies`
- [ ] Validate logging: `tail -20 mecris.log`

### Before Important Sessions
- [ ] Budget check: `curl localhost:8000/usage`
- [ ] Goal status: `curl localhost:8000/beeminder`
- [ ] System health: `curl localhost:8000/health`
- [ ] Recent alerts: `tail mecris.log | grep -i emergency`

---

## 🚨 Known Issues & Workarounds

### Current Limitations
1. **No autonomous sessions yet** - Manual Claude Code integration required
2. **No cron integration** - Manual ping scheduling
3. **Limited error recovery** - Manual restart often needed
4. **No session persistence** - Each Claude session starts fresh
5. **No advanced caching** - Some operations may be slow

### Planned Improvements (Vaporware Alert 🚨)
- **Autonomous ping system** - Scheduled check-ins without manual intervention
- **Advanced budget management** - Automatic operation scaling based on remaining credits
- **Enhanced alert system** - Multi-channel notifications (SMS, email, desktop)
- **Session memory** - Persistent context across Claude sessions
- **Performance optimization** - Caching, connection pooling, async operations
- **Advanced insights** - Pattern recognition, productivity analytics
- **Integration expansion** - Calendar, GitHub, Jira, time tracking tools

---

**Remember**: Mecris is designed to help you live deliberately and act efficiently. Use it daily, trust its warnings, and let it handle the cognitive load of tracking your goals and context.

*This guide evolves with the system. When vaporware becomes reality, update this document.*