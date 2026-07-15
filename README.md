# 🧠 Mecris — Personal LLM Accountability System

> "A containerized mind palace for living deliberately, acting efficiently, and getting the damn goals done."

## What This Is

Mecris is a **persistent cognitive agent system** that extends Claude's narrative thread beyond single sessions. It's designed to help maintain focus, track progress, and provide strategic insight by integrating with your personal data sources.

**This is not a chatbot.** This is a delegation system that helps you stay accountable to your goals and use your time intentionally.

## Quick Start

### 🚀 Local-First (Optimized for Ollama)
Mecris is now optimized for fast, local inference on **Ollama (Gemma 4)** with a token-efficient minimal harness (<1.5k context overhead).

```bash
# Launch the optimized local-first loop
PYTHONPATH=. .venv/bin/python3 py_harness/main.py
```

### 🎯 Using Pi (Open-Source Agent)
The **Pi coding agent** now drives Mecris as a TypeScript extension—bring your own model (Copilot, Groq, Anthropic, Google, local Ollama).

```bash
# One-time setup
cd .pi/extensions/mecris && npm install && cd ../../..

# Launch Pi with Mecris bridge
pi  # Or: pi --provider groq --model llama-3.1-70b-versatile

# In the chat, ask for a status update
> What's my Mecris status?
```

See [docs/PI_MECRIS_GUIDE.md](docs/PI_MECRIS_GUIDE.md) for detailed configuration, lazy-loading, and troubleshooting.

### ☁️ Standard Setup
For detailed setup instructions for different agents, see [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md).

```bash
# 1. Install dependencies using uv
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 2. Configure environment (copy and edit .env.example if needed)
# Set BEEMINDER_USERNAME, BEEMINDER_AUTH_TOKEN, TWILIO credentials, etc.

# 3. Launch the MCP server
./scripts/launch_server.sh

# 4. Test health endpoint
curl http://127.0.0.1:8000/health
```

## Architecture Overview

Mecris is a **cloud-coordinated, local-first** accountability system. It is designed for **maximum resilience**: the local MCP server maintains a direct line to the database and can survive a total loss of the cloud APIs.

```text
                               ┌─────────────────┐
                               │   NEON DB       │
                               │ (Central State) │
                               └─┬─────────────┬─┘
                  (Cloud Path)   │             │   (Local Path)
                ┌────────────────┴──────┐      ▼────────────────┐
                │   CLOUD HUB (WASM API)│      │   LOCAL MCP    │
                ├───────────────────────┤      │ (Python / SQL) │
                │   FREE: FERMYON       │      └──────┬─────────┘
                │   PRO: AKAMAI CRON    │             │
                └───────────┬───────────┘             │
                            │                         │
           ┌────────────────┴─────────────────────────┴──────────────┐
           │              THE STANDARD BUS (JSON / WIT)              │
           └────┬───────────────┬─────────────────┬─────────────┬────┘
                ▼               ▼                 ▼             ▼
         ┌────────────┐  ┌─────────────┐  ┌───────────────┐  ┌─────────────┐
         │ MOBILE GO  │  │ AGENTS/BOTS  │  │ HUMAN / CLI   │  │ CI TRIGGERS │
         │ (Sensors)  │  │ (Narrators)  │  │ (Gemini/Term) │  │ (GHA/Hooks) │
         └────────────┘  └─────────────┘  └───────────────┘  └─────────────┘
```

### Core Components

*   **The Hubs**: Distributed logic centers that manage "Knowledge" (Neon DB) and "Actions" (Twilio/Beeminder).
    *   **Local MCP (Primary)**: Your local Python server. It bridges local data (Obsidian) and maintains a direct connection to Neon. It is the primary interface for humans and narrators.
    *   **Cloud Hub (Failover/Mobile)**: Hosted on Fermyon or Akamai. It provides high-availability API endpoints for the Android app and scheduled cron triggers for autonomous nagging.
*   **The Bus**: All components interact via a language-neutral Standard Bus (JSON/WIT), ensuring that your Android app and your terminal see the same reality.
*   **The Spokes**: Lightweight "Hosts" (Mobile, CLI, and Bots) provide sensors and interfaces to the human.
    *   **Mobile Go**: Android client bridging physical sensors (Google Fit/Health Connect).
    *   **Agents/Bots**: Gemini and Claude narrators that interpret the state and guide the human.
    *   **CI Triggers**: GitHub Actions and webhooks that drive periodic cloud synchronization.
- **Robust startup/shutdown** with process management
- **Enhanced error handling** and logging
- **Industry-Leading Toolset**: Features **34 distinct MCP tools**—a larger specialized toolset than even the standard [GitHub MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/github) (which provides 20+).

## Agent Harnesses

Mecris can be driven by multiple agent harnesses. Each has different tradeoffs (model choice, context size, local-first vs cloud-first, token efficiency).

| Harness | Model Backend | Local-First? | Token Efficiency | Status | Docs |
|---|---|---|---|---|---|
| **py_harness** | Ollama (Gemma 4, Qwen) | ✅ Yes | ⭐⭐⭐ (1.5k core) | ✅ Active | [py_harness/README.md](py_harness/README.md) |
| **Pi (TypeScript extension)** | Any (Copilot, Groq, Anthropic, Google, local) | Optional | ⭐⭐ (5 tools + loader) | ✅ Active | [docs/PI_MECRIS_GUIDE.md](docs/PI_MECRIS_GUIDE.md) |
| **Claude Code** | Claude models | ❌ No | ⭐⭐ (all 34 tools) | ✅ Active | [.mcp.json](.mcp.json) |
| **Gemini CLI** | Gemini models | ❌ No | ⭐⭐ (all 34 tools) | ✅ Active | [.gemini/settings.json](.gemini/settings.json) |
| **Antigravity CLI** | Gemini models | ❌ No | ⭐⭐ (all 34 tools) | ✅ Active | [.gemini/antigravity-cli/](docs/) |

**Pick your harness:**
- **Local + fast?** Use `py_harness` (Ollama on your machine)
- **Multi-model + vendor-agnostic?** Use **Pi** (bring your own model/provider)
- **Specific vendor?** Use Claude Code (Claude), Gemini CLI (Gemini), or Antigravity (Gemini)

See [docs/PI_HARNESS_ROADMAP.md](docs/PI_HARNESS_ROADMAP.md) for detailed parity matrix and architectural differences.

**Tool Categories:**
- **Strategic Context**: `get_narrator_context`, `get_coaching_insight`
- **Goal Mastery**: `get_beeminder_status`, `trigger_language_sync`, `get_language_velocity_stats`
- **Physical Accountability**: `get_daily_activity`, `get_weather_report`
- **Financial Stewardship**: `get_budget_status`, `get_real_anthropic_usage`, `get_unified_cost_status`
- **System Health**: `get_system_health`, `get_scheduler_queue`, `trigger_reminder_check`
- **Daily Progress**: `get_daily_aggregate_status` (The Majesty Cake 🍰)

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
- **Neon (Postgres)** for cloud-native persistence and multi-tenant isolation.
- **Accurate cost calculation** using official Anthropic pricing
- **Real-time budget tracking** via Anthropic Admin API and Neon.
- **Alert system** via Twilio for critical budget states
- **Historical analysis** and burn rate projection

#### ✅ Twilio Alerts - **CONFIGURED**
- SMS notifications for beemergencies and budget alerts
- Integrated with background task processing
- Configurable alert thresholds

#### ✅ Obsidian Integration - **CONFIGURED**
- File reading capabilities implemented
- Vault structure parsing in progress

### 3. Server Management Tools ✅ **COMPLETE**
- **`scripts/launch_server.sh`** - Safe server startup with health checks
- **`scripts/shutdown_server.sh`** - Graceful shutdown with cleanup
- **Process management** with PID files and cleanup traps
- **Health monitoring** with automatic service validation

## Current State

### ✅ Production Ready
- **MCP Server**: Secure, robust, stdio-integrated
- **Beeminder Integration**: Live API, comprehensive testing
- **Budget Tracking**: Real-time via Anthropic Admin API and Neon (Postgres)
- **Alert System**: Twilio SMS for critical notifications
- **Coordination**: Distributed leader election across instances

### 🚧 In Progress  
- **Obsidian Integration**: Vault parsing and goal extraction
- **Documentation**: Organized into `/docs` directory

### 📋 Next Priorities
- **Majesty Cake UI**: Implement the visual reward widget in the Android app.
- **Multi-User Twilio**: Migrate Twilio logic to the WASM brain for full multi-tenancy.
- **Rust Reminder Engine**: Port heuristic logic from Python to Rust/WASM.

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

## Operation Mode

Mecris currently operates in **Stdio Mode**, integrated directly with CLI agents (Gemini CLI, Claude Code).

### Running in Stdio Mode
The server is invoked automatically by your agent using:
```bash
python mcp_stdio_server.py
```

### Future: Secure SSE Mode
Standalone FastAPI/SSE mode is currently disabled and will be reintroduced once secured with OIDC authentication.

## Testing

### Run All Tests
```bash
source .venv/bin/activate
PYTHONPATH=. pytest
```

### Manual Tool Testing
You can test the MCP tools directly via your agent's command interface (e.g., `/get_narrator_context`).

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

### Current Budget: $20.88 remaining (as of April 2026)
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