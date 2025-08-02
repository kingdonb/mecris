# 🧠 Mecris System Guide
## The Not-a-Torment-Nexus Personal Accountability Platform

> "This isn't dystopia, it's **delegation**."

---

## 🎯 What Is Mecris?

Mecris (Greek: μακρύς - "long, extended") is a **persistent cognitive agent system** designed to help you live deliberately, act efficiently, and get your goals done. It's your digital narrator - not a chatbot, but a **strategic oversight system** that aggregates multiple accountability mechanisms into unified context.

## 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Claude Code   │────│  Mecris Server  │────│  Context APIs   │
│   (Narrator)    │    │   (FastAPI)     │    │   (MCP Clients) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                        ┌───────┼───────┐
                        │       │       │
                   ┌─────▼──┐ ┌─▼──┐ ┌──▼─────┐
                   │Obsidian│ │Bee │ │ Twilio │
                   │  Vault │ │mind│ │ Alerts │
                   └────────┘ └────┘ └────────┘
```

### Core Components

1. **MCP Server** (`mcp_server.py`) - Central FastAPI application
2. **Obsidian Client** (`obsidian_client.py`) - Goals and todos extraction  
3. **Beeminder Client** (`beeminder_client.py`) - Goal tracking and derailment detection
4. **Claude Monitor** (`claude_monitor.py`) - Budget tracking and burn rate analysis
5. **Twilio Sender** (`twilio_sender.py`) - SMS alerts for emergencies

---

## 🚀 Quick Start

### 1. Environment Setup

Create `.env` file:
```bash
# Obsidian MCP Connection
OBSIDIAN_MCP_HOST=localhost
OBSIDIAN_MCP_PORT=3001
OBSIDIAN_VAULT_PATH=/path/to/your/vault

# Beeminder API
BEEMINDER_USERNAME=your_username
BEEMINDER_AUTH_TOKEN=your_auth_token

# Twilio Alerts
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=+1234567890
TWILIO_TO_NUMBER=+1234567890

# Claude Budget Tracking
CLAUDE_BUDGET_LIMIT=25.00
CLAUDE_EXPIRY_DATE=2025-08-05
CLAUDE_USAGE_FILE=claude_usage.json

# Server Config
PORT=8000
DEBUG=false
```

### 2. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Start The Server

```bash
python mcp_server.py
```

Server runs at `http://localhost:8000`

---

## 📊 API Endpoints

### Health & Status
- `GET /` - Basic server info
- `GET /health` - Comprehensive health check of all services

### Obsidian Integration
- `GET /goals` - Extract goals from vault
- `GET /todos` - Extract todos with completion status
- `GET /daily/{date}` - Get daily note content (YYYY-MM-DD)

### Beeminder Integration  
- `GET /beeminder/status` - Overall goal portfolio status
- `GET /beeminder/emergency` - Goals requiring immediate attention
- `POST /beeminder/alert` - Check for emergencies and send SMS

### Claude Budget Tracking
- `GET /budget/status` - Current credit usage and projections
- `POST /budget/track` - Record usage costs manually
- `POST /budget/alert` - Check budget and send low-credit alerts

### Unified Context
- `GET /narrator/context` - **Main endpoint** - Strategic summary for Claude narrator
- `POST /log-session` - Log session summary back to Obsidian

---

## 🧾 Key Features Explained

### 1. **Goals & Todos Extraction**
- Parses Obsidian vault for goal patterns (`## Goals`, `- [ ] Goal:`)
- Extracts markdown todos with priority and tags
- Deduplicates across files
- Tracks completion status

### 2. **Beeminder Derailment Detection**
- Classifies goals by risk: `CRITICAL` | `WARNING` | `CAUTION` | `SAFE`
- Calculates time remaining until derailment
- Generates actionable emergency alerts
- Sorts by urgency for prioritization

### 3. **Claude Budget Management**
- Tracks credit usage with daily burn rate calculation
- Projects days remaining until budget/expiry
- Sends SMS alerts at configurable thresholds
- Maintains usage history for analysis

### 4. **SMS Alert System**
- Beemergency notifications for critical goals
- Budget warnings when credits run low
- Configurable urgency levels and thresholds
- WhatsApp support via Twilio sandbox

### 5. **Narrator Context Aggregation**
- Unified strategic summary from all data sources
- Risk assessment and priority recommendations
- Budget-aware advice (focus on high-value work when credits low)
- Session logging for memory persistence

---

## ⚙️ Configuration Guide

### Obsidian Setup
1. Install `mcp-obsidian` server
2. Configure MCP client connection
3. Set vault path in environment
4. Ensure goal/todo patterns in notes

### Beeminder Setup
1. Get API token from beeminder.com/api
2. Add username and token to `.env`
3. Goals automatically tracked once configured

### Twilio Setup
1. Create Twilio account
2. Get phone number for SMS sending
3. Add credentials to `.env`
4. Test with `python twilio_sender.py`

### Claude Budget Setup
1. Set budget limit and expiry date
2. Usage file tracks spending automatically
3. Manual tracking via `/budget/track` endpoint

---

## 🔍 Usage Patterns

### For Claude Code Integration
```python
# Get strategic context
context = requests.get("http://localhost:8000/narrator/context").json()

# Check for emergencies
if context["urgent_items"]:
    print("🚨 URGENT:", context["urgent_items"])

# Budget-aware recommendations
if context["budget_status"]["days_remaining"] < 2:
    print("⚠️ BUDGET CONSTRAINT - Focus on critical work only")
```

### Manual Budget Tracking
```bash
# Track session cost
curl -X POST "http://localhost:8000/budget/track" \
  -H "Content-Type: application/json" \
  -d '{"cost": 2.15, "description": "Morning planning session"}'

# Check current status
curl http://localhost:8000/budget/status
```

### Emergency Monitoring
```bash
# Check for beemergencies
curl http://localhost:8000/beeminder/emergency

# Force alert check
curl -X POST http://localhost:8000/beeminder/alert
```

---

## 🛠️ Testing Your Setup

### 1. Health Check
```bash
curl http://localhost:8000/health
```
Should return `"healthy"` status for all configured services.

### 2. Test Goals Extraction
```bash
curl http://localhost:8000/goals
```
Should return parsed goals from your Obsidian vault.

### 3. Test Budget Tracking
```bash
curl http://localhost:8000/budget/status
```
Should return current credit status and projections.

### 4. Test SMS Alerts
```bash
python twilio_sender.py
```
Should send test message to configured number.

### 5. Test Unified Context
```bash
curl http://localhost:8000/narrator/context
```
Should return comprehensive strategic summary.

---

## 🔧 Troubleshooting

### Common Issues

**1. Obsidian MCP Connection Failed**
- Ensure `mcp-obsidian` server is running on port 3001
- Check vault path is correct
- Verify MCP server has read access to vault

**2. Beeminder API Errors**
- Verify username and auth token are correct
- Check API rate limits
- Ensure goals exist in your Beeminder account

**3. SMS Alerts Not Sending**
- Verify all Twilio credentials in `.env`
- Check phone number format (+1234567890)
- Ensure Twilio account has sufficient credits

**4. Budget Tracking Issues**
- Check `claude_usage.json` file permissions
- Verify expiry date format (YYYY-MM-DD)
- Ensure budget limit is set correctly

### Debug Mode
Set `DEBUG=true` in `.env` for verbose logging.

---

## 🎯 Strategic Usage

### Morning Planning
1. Check `/narrator/context` for overnight changes
2. Review urgent items and beemergencies
3. Assess budget constraints for the day
4. Plan high-value work if credits are low

### During Work Sessions
1. Use budget tracking for cost awareness
2. Monitor beemergency alerts
3. Focus on critical goals when time-constrained

### End of Day
1. Log session summary via `/log-session`
2. Update todos and goals in Obsidian
3. Check tomorrow's beemergencies

---

## 🚨 Emergency Protocols

### Beemergency Response
1. **CRITICAL** (derailing today): Drop everything, enter data immediately
2. **WARNING** (derails tomorrow): Schedule data entry today
3. **CAUTION** (derails in 2-3 days): Plan data collection

### Budget Crisis Response
1. **<1 day remaining**: Finish only critical work, no exploration
2. **<2 days remaining**: Focus on highest-value tasks only
3. **<5 days remaining**: Begin wrapping up, no new projects

---

## 📈 Future Enhancements

### Planned Features
- GitHub Issues integration
- Jira board connectivity
- Enhanced goal tracking with sub-goals
- Automated session cost calculation
- Historical trend analysis
- Custom alert thresholds

### Integration Opportunities
- Calendar sync for time-based goals
- Email parsing for action items
- Slack notifications
- Habit tracking integration

---

## 🏁 Success Metrics

Mecris is working when:
- ✅ You never miss a Beeminder derailment
- ✅ You stay within Claude budget constraints  
- ✅ Goals and todos stay current and actionable
- ✅ You receive timely alerts for urgent items
- ✅ Sessions are logged for future reference
- ✅ Strategic decisions are data-informed

---

*"The best system is the one that makes the right choice the easiest choice."*