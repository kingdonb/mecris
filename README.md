# 🧠 Mecris — Personal LLM Accountability System

> "A containerized mind palace for living deliberately, acting efficiently, and getting the damn goals done."

## What This Is

Mecris is a **persistent cognitive agent system** that extends Claude's narrative thread beyond single sessions. It's designed to help maintain focus, track progress, and provide strategic insight by integrating with your personal data sources.

**This is not a chatbot.** This is a delegation system that helps you stay accountable to your goals and use your time intentionally.

## Quick Start

```bash
# 1. Install dependencies
source venv/bin/activate && pip install -r requirements.txt

# 2. Configure environment (copy and edit .env.example if needed)
# Set BEEMINDER_USERNAME, BEEMINDER_AUTH_TOKEN, TWILIO credentials, etc.

# 3. Launch the MCP server
./scripts/launch_server.sh

# 4. Test health endpoint
curl http://127.0.0.1:8000/health

# 5. Get narrator context
curl http://127.0.0.1:8000/narrator/context
```

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Claude Code   │◄──►│  FastAPI MCP     │◄──►│  Data Sources   │
│   (Narrator)    │    │   Server         │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ├─ Obsidian Vault
                       ┌──────────────┐                 ├─ Beeminder API  ✅
                       │   Twilio     │                 ├─ Claude Monitor ✅
                       │   Alerts     │                 └─ Usage Tracker  ✅
                       └──────────────┘
```

## Core Components

### 1. FastAPI MCP Server ✅ **PRODUCTION READY**
- **Health endpoint** with service status monitoring
- **Secure localhost binding** (127.0.0.1 only)
- **Robust startup/shutdown** with process management
- **Enhanced error handling** and logging

**Key Endpoints:**
- `GET /health` - Service health and dependency status
- `GET /narrator/context` - Unified context for Claude narrator
- `GET /beeminder/status` - Goal portfolio with risk assessment
- `GET /usage` - Budget status and burn rate analysis
- `POST /beeminder/alert` - Emergency goal notifications
- `POST /usage/record` - Track API usage sessions

### 2. Data Source Integrations

#### ✅ Beeminder API - **FULLY TESTED**
- **Live API integration** with real goal data
- **Risk classification** (CRITICAL/WARNING/CAUTION/SAFE)
- **Emergency detection** with urgency levels
- **Runway analysis** prioritizing urgent goals
- **No mock data** - verified via comprehensive test suite

#### ✅ Usage Tracking - **PRODUCTION READY**
- **SQLite database** for session storage
- **Accurate cost calculation** using official Anthropic pricing
- **Budget management** with manual updates
- **Alert system** via Twilio for critical budget states
- **Historical analysis** and burn rate projection

#### ✅ Twilio Alerts - **CONFIGURED**
- SMS notifications for beemergencies and budget alerts
- Integrated with background task processing
- Configurable alert thresholds

#### 🚧 Obsidian Integration - **PARTIAL**
- File reading capabilities implemented
- Vault structure parsing in progress

### 3. Server Management Tools ✅ **COMPLETE**
- **`scripts/launch_server.sh`** - Safe server startup with health checks
- **`scripts/shutdown_server.sh`** - Graceful shutdown with cleanup
- **Process management** with PID files and cleanup traps
- **Health monitoring** with automatic service validation

## Current State

### ✅ Production Ready
- **MCP Server**: Secure, robust, health-monitored
- **Beeminder Integration**: Live API, comprehensive testing
- **Budget Tracking**: Local SQLite with manual updates
- **Alert System**: Twilio SMS for critical notifications
- **Server Management**: Professional startup/shutdown scripts

### 🚧 In Progress  
- **Obsidian Integration**: Vault parsing and goal extraction
- **Documentation**: Organized into `/docs` directory

### 📋 Next Priorities
- **Claude API Balance Scraper**: Automated balance retrieval
- **Periodic Check-ins**: Cron-based autonomous sessions
- **Enhanced Narrator Context**: Deeper strategic insights

## Design Principles

1. **Read Before Writing**: No hallucinations, context window is sacred
2. **Budget Conscious**: Every token costs money
3. **Warning System**: Professional doomsaying for deadline risks  
4. **Memory Persistence**: Leave breadcrumbs for future sessions
5. **Strategic Focus**: Insight and path illumination, not just task completion

## Project Structure

```
mecris/
├── README.md                 # This file
├── CLAUDE.md                 # Core narrator instructions
├── requirements.txt          # Python dependencies
├── start_server.py          # Main server entry point
├── mcp_server.py            # FastAPI application
├── scripts/                 # Server management scripts
│   ├── launch_server.sh     # Safe server startup
│   └── shutdown_server.sh   # Graceful shutdown
├── tests/                   # Test suites
│   ├── test_mecris.py       # System integration tests
│   └── test_beeminder_live.py # Beeminder API tests
├── logs/                    # Application logs and reports
├── docs/                    # Technical documentation
└── [data clients]           # beeminder_client.py, usage_tracker.py, etc.
```

## Server Management

### Start Server
```bash
./scripts/launch_server.sh
# Server starts on http://127.0.0.1:8000
# Includes health checks and background monitoring
```

### Stop Server
```bash
./scripts/shutdown_server.sh        # Graceful shutdown
./scripts/shutdown_server.sh --force # Force kill if needed
./scripts/shutdown_server.sh --status # Check server status
```

### Health Check
```bash
curl http://127.0.0.1:8000/health
# Returns service status and dependency health
```

## Testing

### Run All Tests
```bash
source venv/bin/activate
python tests/test_mecris.py        # Full system test
python tests/test_beeminder_live.py # Beeminder integration test
```

### Manual API Testing
```bash
# Get narrator context
curl http://127.0.0.1:8000/narrator/context

# Check budget status  
curl http://127.0.0.1:8000/usage

# Beeminder emergency check
curl -X POST http://127.0.0.1:8000/beeminder/alert
```

## Configuration

Set these environment variables in your shell or `.env` file:

```bash
# Beeminder Integration
BEEMINDER_USERNAME=your_username
BEEMINDER_AUTH_TOKEN=your_token

# Twilio Alerts  
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=+1234567890
TWILIO_TO_NUMBER=+1234567890

# Optional Configuration
DEBUG=false                    # Enable debug logging
HOST=127.0.0.1                # Server bind address  
PORT=8000                     # Server port
LOG_LEVEL=INFO                # Logging level
```

## Budget Management

### Current Budget: $18.21 remaining (as of Aug 2025)
- **Daily burn rate**: Automatically calculated from usage
- **Budget alerts**: SMS notifications for critical states
- **Manual updates**: Use `/usage/update_budget` endpoint

### Update Budget
```bash
curl -X POST http://127.0.0.1:8000/usage/update_budget \
  -H "Content-Type: application/json" \
  -d '{"remaining_budget": 15.50}'
```

## Documentation

- **`CLAUDE.md`** - Core narrator instructions and context
- **`CLAUDE_CODE_INTEGRATION.md`** - Integration with Claude Code CLI
- **`docs/CLAUDE_API_LIMITATIONS.md`** - Budget tracking approach
- **`docs/`** - Additional technical documentation

## Support

For issues or questions:
- Check server logs in `logs/` directory
- Run health checks to diagnose problems
- Review test output for integration issues