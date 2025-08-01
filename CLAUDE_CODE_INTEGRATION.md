# 🤖 Claude Code + Mecris Integration Guide

## 🎯 Quick Start for Claude Sessions

**URL**: `http://localhost:8000/narrator/context`  
**Purpose**: Get strategic insights and goal awareness in any Claude Code session

### Essential Commands for Claude

```bash
# 1. Check if Mecris is running
curl -s http://localhost:8000/health

# 2. Get narrator context (main command)
curl -s http://localhost:8000/narrator/context | python3 -m json.tool

# 3. Check specific Beeminder status  
curl -s http://localhost:8000/beeminder/status

# 4. Check budget status
curl -s http://localhost:8000/budget/status
```

## 📊 Real Narrator Context Example

```json
{
  "summary": "Active goals: 0, Pending todos: 0, Beeminder goals: 10, Budget: 1.1 days left",
  "goals_status": {"total": 0, "sources": ["obsidian"]},
  "urgent_items": ["BUDGET WARNING: 1.1 days left"],
  "beeminder_alerts": ["Derails tomorrow - act today", "Derails in 2 days"],
  "budget_status": {
    "status": "⚠️ WARNING",
    "credits_remaining": 0.98,
    "days_remaining": 1.08,
    "daily_burn": 0.91
  },
  "recommendations": [
    "Urgent: Focus on highest-value work due to budget constraints",
    "No active goals found - consider setting objectives"
  ]
}
```

## 🧠 How Claude Should Use This Data

### 1. **Budget Awareness** (Critical)
- Check `budget_status.days_remaining` 
- If < 2 days: Prioritize high-value work
- If < 1 day: Focus only on critical tasks
- Use `daily_burn` to estimate session costs

### 2. **Goal Monitoring** 
- `beeminder_alerts` shows which goals need attention
- `urgent_items` contains time-sensitive actions
- Cross-reference with Kingdon's current work priorities

### 3. **Strategic Recommendations**
- `recommendations` array provides context-aware suggestions
- Adapt work approach based on constraints and opportunities

## 🔄 Integration Patterns

### Pattern 1: Session Start Context
```python
# At start of any significant Claude Code session:
import requests
context = requests.get('http://localhost:8000/narrator/context').json()
print(f"Budget: {context['budget_status']['days_remaining']:.1f} days")
print(f"Alerts: {context['beeminder_alerts']}")
```

### Pattern 2: Decision Points
- Before starting large tasks: Check budget status
- Before context-heavy research: Verify time constraints  
- During planning: Incorporate Beeminder deadlines

### Pattern 3: Progress Tracking
```bash
# Log significant completions back to Mecris
curl -X POST http://localhost:8000/log-session \
  -H "Content-Type: application/json" \
  -d '{"duration": "45min", "actions_taken": ["implemented X"], "outcomes": "Y completed"}'
```

## 🎛️ Server Management

### Start Mecris Server
```bash
cd /Users/yebyen/w/mecris
source venv/bin/activate
python mcp_server.py
```

### Verify All Systems
```bash
# Health check
curl -s http://localhost:8000/health | python3 -m json.tool

# Expected: beeminder="ok", claude_monitor="not_configured" (acceptable)
```

## 🔒 Security Notes
- **READ-ONLY**: All Beeminder operations are GET-only
- No POST/DELETE endpoints exposed for goal modification
- Budget tracking is local to Mecris system

## 💡 Advanced Usage

### Custom Endpoint Queries
```bash
# Get specific Beeminder emergencies
curl -s http://localhost:8000/beeminder/emergency

# Track usage manually  
curl -X POST http://localhost:8000/budget/track -d '{"cost": 0.25, "description": "research task"}'

# Get today's daily note (if Obsidian configured)
curl -s http://localhost:8000/daily/$(date +%Y-%m-%d)
```

## 🎯 Success Metrics
- **Budget efficiency**: Stay within daily targets
- **Goal awareness**: Reference Beeminder alerts in decisions  
- **Strategic alignment**: Use recommendations to guide work
- **Autonomous operation**: Claude can operate without re-setup

---
**Status**: Production-ready | **Test Score**: 85.7% | **Budget Integration**: ✅ Active