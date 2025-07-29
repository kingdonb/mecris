# 🧠 Mecris — Personal LLM Accountability System

> "A containerized mind palace for living deliberately, acting efficiently, and getting the damn goals done."

## What This Is

Mecris is a **persistent cognitive agent system** that extends Claude's narrative thread beyond single sessions. It's designed to help maintain focus, track progress, and provide strategic insight by integrating with your personal data sources.

**This is not a chatbot.** This is a delegation system that helps you stay accountable to your goals and use your time intentionally.

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Claude Code   │◄──►│  FastAPI MCP     │◄──►│  Data Sources   │
│   (Narrator)    │    │   Server         │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ├─ Obsidian Vault
                       ┌──────────────┐                 ├─ Beeminder API
                       │   Twilio     │                 ├─ Claude Monitor
                       │   Alerts     │                 └─ Time Tracker
                       └──────────────┘
```

## Core Components

### 1. FastAPI Machine Context Provider (MCP) Server
- **Purpose**: Central hub for structured personal data access
- **Endpoints**:
  - `/goals` - Current objectives and priorities
  - `/todos` - Task lists and completion status
  - `/daily/YYYY-MM-DD` - Daily notes and reflections
  - `/beeminder` - Goal derailment alerts
  - `/usage` - Claude credit burn rate and budget status
- **Config**: Environment-driven, optional logging

### 2. Data Source Integrations
- **Obsidian Vault**: Markdown files for notes, goals, decision logs
- **Beeminder**: Goal tracking with hard deadlines ("beemergencies")
- **Twilio**: SMS alerts for critical notifications
- **Claude Monitor**: Real-time API usage and cost tracking
- **Time Tracker**: Work/life balance monitoring (40hr/week target)

### 3. Autonomous Operation System
- **Periodic Pings**: Cron-triggered sessions for progress updates
- **File-Based Memory**: Symbolic persistence between sessions
- **Strategic Narration**: Context-aware insights, not just summaries

## Current State

### ✅ Completed
- Initial CLAUDE.md context and mission definition
- Twilio SMS sender implementation (`twilio_sender.py`)
- Python dependencies framework (`requirements.txt`)

### 🚧 In Progress
- FastAPI MCP server architecture
- Obsidian markdown file loading
- Beeminder API integration planning

### 📋 Planned
- Claude usage monitoring dashboard
- Time tracker integration
- Automated "beemergency" alerts
- Cron-based autonomous check-ins

## Design Principles

1. **Read Before Writing**: No hallucinations, context window is sacred
2. **Budget Conscious**: Every token costs money
3. **Warning System**: Professional doomsaying for deadline risks  
4. **Memory Persistence**: Leave breadcrumbs for future sessions
5. **Strategic Focus**: Insight and path illumination, not just task completion

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env  # (when created)

# Run the MCP server
python -m uvicorn mcp_server:app --reload

# Test Twilio integration
python twilio_sender.py "Test message"
```

## Budget & Constraints

- **Target**: Stay under $1 initial budget
- **Philosophy**: Waste not, want not
- **Time Constraint**: 40hr/week work limit (currently untracked systematically)
- **Autonomous Goals**: Periodic contributions via cron pings

## Next Steps

The immediate priority is building the FastAPI MCP server that will serve as the data backbone for the Claude narrator system. This will enable structured access to personal contexts without manual data loading in each session.