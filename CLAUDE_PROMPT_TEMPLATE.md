# 🎯 Claude Code Session Prompt Template

## Copy-Paste This Into Future Claude Sessions

```
I'm working on a project with a running Mecris system that provides goal tracking and budget monitoring. Before we start, let me check the current context:

curl -s http://localhost:8000/narrator/context

Based on this data, I need you to:
1. **Budget Awareness**: Check days_remaining and adjust work scope accordingly
2. **Goal Integration**: Reference any beeminder_alerts in our planning
3. **Strategic Focus**: Use the recommendations to guide our priorities

Key integration points:
- Mecris server running at localhost:8000  
- Use /narrator/context for strategic insights
- Log major completions via /log-session endpoint
- Budget-conscious: Optimize for high-value work if time is limited

The system tracks my Beeminder goals and Claude usage budget. Please factor this context into all planning and decision-making.

Ready to proceed with [specific task]?
```

## 🔧 Quick Validation Commands

Before starting any session, run these to verify Mecris:
```bash
# 1. Health check
curl -s http://localhost:8000/health

# 2. Get context
curl -s http://localhost:8000/narrator/context | python3 -m json.tool

# 3. Verify Beeminder goals
curl -s http://localhost:8000/beeminder/status
```

## 🎛️ If Mecris Isn't Running

```bash
cd /Users/yebyen/w/mecris
source venv/bin/activate  
python mcp_server.py &

# Wait 3 seconds then test
sleep 3 && curl -s http://localhost:8000/health
```

## 📊 Understanding the Context Response

- **urgent_items**: Time-sensitive actions (budget warnings, derail risks)
- **beeminder_alerts**: Goals needing attention ("Derails tomorrow")  
- **recommendations**: Strategic guidance based on current state
- **budget_status**: Credits remaining and daily burn rate

## 🎯 Session Types

### Research/Analysis Sessions
- Check budget first - these are token-heavy
- Use context to focus on high-priority topics
- Reference Beeminder goals for relevance

### Implementation Sessions  
- Budget less critical for focused coding
- Log completions via /log-session
- Check for goal alignment before starting

### Planning Sessions
- Always start with full narrator context
- Factor in time constraints and deadlines
- Use recommendations to set priorities

---
**Usage**: Copy the main prompt template for consistent Mecris integration across all Claude Code sessions.