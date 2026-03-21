# 🛠️ Mecris Operations Guide

> **"Your daily field manual for running a containerized mind palace"**

This is your practical guide to operating Mecris day-to-day. Not theory, not architecture — just the commands, workflows, and procedures you need to keep your cognitive agent system running smoothly.

---

## 🚀 Quick Start (Daily Startup)

### 1. System Health Check
```bash
# Check if MCP server is running
curl -s http://localhost:8000/health || echo "Server down"

# Verify multi-tenant status
curl -s "http://localhost:8000/narrator/context?user_id=YOUR_SUB" | head -20
```

### 2. Start/Restart Mecris
```bash
# Full system startup (includes background scheduler)
python start_server.py

# Distributed Leader Check (Who is running background tasks?)
curl -s http://localhost:8000/mcp/scheduler/queue
```

### 3. Verify Your Context
```bash
# Get full narrator context (what Claude sees)
curl -s "http://localhost:8000/narrator/context?user_id=USER_SUB"

# Check budget status
curl -s "http://localhost:8000/budget/status?user_id=USER_SUB"

# Emergency check (any goals derailing?)
curl -s "http://localhost:8000/beeminder?user_id=USER_SUB" | grep -i "emergency\|derail"
```

---

## 📋 Daily Operational Workflows

### Morning Ritual (5 minutes)
```bash
# 1. System status
curl -s "http://localhost:8000/narrator/context?user_id=USER_SUB" | grep -A5 "Budget\|Emergency\|Goals"

# 2. Check for overnight alerts
tail -20 mecris.log | grep -i "alert\|emergency\|derail"
```

### Midday Check-in (2 minutes)
```bash
# Quick pulse check
curl -s "http://localhost:8000/narrator/context?user_id=USER_SUB" | head -10
```

### Evening Wrap-up (10 minutes)
```bash
# 1. Log today's progress
# (User provides summary via MCP tool / session log)

# 2. Check tomorrow's risks
curl -s "http://localhost:8000/beeminder?user_id=USER_SUB" | grep -B2 -A2 "tomorrow"
```

---

## 🎯 Core Operational Commands

### Multi-Tenant Context Retrieval
```bash
# Full narrator context for a specific user
curl -s "http://localhost:8000/narrator/context?user_id=USER_SUB"

# Specific data sources (User-scoped)
curl -s "http://localhost:8000/budget/status?user_id=USER_SUB"
curl -s "http://localhost:8000/goals?user_id=USER_SUB"
curl -s "http://localhost:8000/obsidian/goals"
```

### Background Task Management
```bash
# Check if background sync is running
curl -s http://localhost:8000/mcp/scheduler/queue

# Trigger manual walk sync to Beeminder
curl -X POST http://localhost:8000/mcp/sync/walks
```

### System Diagnostics
```bash
# Server health
curl -s http://localhost:8000/health

# View recent session logs
tail -50 mecris.log
```

---

## ⚡ Emergency Procedures

### WhatsApp Delivery Issues
1. **Check Delivery Status**:
   ```bash
   python scripts/debug_twilio_messages.py
   ```

2. **Verify Approved Templates**:
   Check `data/approved_templates.json`. Ensure the SID is present and maps to a confirmed working template like `mecris_status_v2`.

3. **Force Reminder Trigger**:
   ```bash
   curl -X POST "http://localhost:8000/intelligent-reminder/trigger?user_id=USER_SUB"
   ```

### Beemergency Response
1. **Immediate Alert Check**:
   ```bash
   curl -s "http://localhost:8000/beeminder?user_id=USER_SUB" | grep -C3 "emergency"
   ```

### Budget Exhaustion Response
1. **Check Remaining Budget**:
   ```bash
   curl -s "http://localhost:8000/budget/status?user_id=USER_SUB" | grep -i "remaining"
   ```

---

## 🔄 Autonomous Operation

### Background Sync (Distributed)
Mecris uses a distributed leader election pattern via Neon DB.
- **Election**: Only one process per user claims the `leader` role in `scheduler_election`.
- **Tasks**: The leader performs background Clozemaster syncs and walk inferences.
- **Heartbeat**: Android clients report heartbeats; the system sends alerts if a client goes dark for > 4 hours.

### Cron Integration
Autonomous reminders are triggered via `setup_reminder_cron.sh`, which hits the local MCP endpoint every 30 minutes.

---

**Remember**: Every operation is now scoped by `user_id`. Ensure your environment variables or API calls include the correct ID to maintain data isolation.

*This guide evolves with the system. Multi-tenancy is now a reality.*
