# 🏗️ Mecris Architecture

*System design for autonomous SMS-based accountability system*

> **Vision**: Mecris operates as an invisible, always-available accountability partner accessible entirely through SMS conversations. Users don't know or care about the technical infrastructure - they simply text their accountability system and receive intelligent, context-aware responses.

## Overview

Mecris is a production-grade accountability system featuring a 30-tool MCP server and a WASM-based cloud brain that:
- Acts as a **Persistence Hub** managing a central Neon Postgres database.
- Runs **Time-Driven** logic (Akamai Cron) for autonomous nagging and failover.
- Provides **Event-Driven** endpoints (Fermyon) for on-demand synchronization.
- Integrates seamlessly with personal data sources (Health Connect, Google Fit, Obsidian).
- Operates under a **State-over-Streams** observability mandate.

## System Architecture

The architecture follows a **Hub-and-Spoke** model. The Hub (WASM API) serves as the "source of truth," while diverse Hosts (Mobile, Python, Agents) act as sensors and interfaces.

```text
                               ┌─────────────────┐
                               │   NEON DB       │
                               │ (Central State) │
                               └────────┬────────┘
                                        │
                ┌───────────────────────┴───────────────────────┐
                │        THE PERSISTENCE HUB (WASM API)         │
                ├───────────────────────┬───────────────────────┤
                │   FREE: FERMYON       │   PRO: AKAMAI CRON    │
                │  (Event-Driven)       │  (Scheduled Logic)    │
                └───────────┬───────────┴───────────┬───────────┘
                            │                       │
           ┌────────────────┴───────────────────────┴────────────────┐
           │             THE STANDARD BUS (JSON / WIT)               │
           └────┬───────────────┬─────────────────┬─────────────┬────┘
                ▼               ▼                 ▼             ▼
         ┌────────────┐  ┌─────────────┐  ┌───────────────┐  ┌─────────────┐
         │ MOBILE GO  │  │  LOCAL MCP  │  │ AGENTS/BOTS   │  │ CI TRIGGERS │
         │ (Sensors)  │  │ (RAG / FS)  │  │ (Narrators)   │  │ (GHA/Hooks) │
         └─────┬──────┘  └──────┬──────┘  └───────────────┘  └─────────────┘
```

## Core Components

### The Persistence Hub (Cloud Layer)
- **Fermyon Cloud**: The primary reactive layer. Handles HTTP triggers from the Android app, Python MCP, and Narrators.
- **Akamai Functions**: The proactive layer. Implements native `spin aka cron` triggers to check goal status and send reminders when local devices are offline.
- **WASM Brain**: Core business logic (Review Pump, Budget Governor) is vacuumed into language-neutral WASM components to ensure identical execution across all cloud providers.

### The Host Layer (Local & Mobile)
- **Mobile Host (Android)**: Captures high-fidelity physical data (steps, exercise) and provides the primary UI for "The Majesty Cake."
- **Local Host (Python MCP)**: Bridges the global cloud state with private local data (Obsidian vault, filesystem). 
- **Narrator Interface**: Directly consumes the `get_narrator_context` tool to provide strategic guidance to the human.

### Observability: State over Streams
Per the **Observability Mandate**, Mecris rejects the "log-searching hole" of unstructured CloudWatch streams.
- **Structured Events**: Every decision (skipping a nag, choosing a model) must be recorded as a queryable database event.
- **Heartbeat Reports**: Heartbeats in `scheduler_election` must include `last_status` and `last_error` to enable `kubectl describe`-style system inspections.

## Deployment Architecture
...
### Production Environment
- **Multi-Cloud/Hybrid Deployment**:
  - **Daily EC2 (Legacy/Heavy)**: Daily 5-hour operational window for heavy processing and archival.
  - **Fermyon Cloud (Standard)**: Primary WASM-based cloud triggers.
  - **Akamai Functions (Trial)**: Experimenting with persistent cron triggers for reminders and failover syncing.
  - **Local/Home Server**: Home-based execution via MCP bridge.
  - **SpinKube**: Ready for Kubernetes-native execution.
- **Health Monitoring**: Unified `system_pulse` and process status reporting via `scheduler_election` table.

### Autonomous Operation
- **Scheduled Compute**: 5-hour daily operational window (7am-12pm ET)
- **Cron-based Health Checks**: Periodic system status and alert processing
- **Self-healing**: Automatic restart and error recovery
- **Graceful Degradation**: Continues operating when external services fail

## SMS Conversation Design

### Natural Language Interface
- **Conversational Flow**: SMS feels like texting a knowledgeable friend
- **Context Awareness**: Remembers previous conversations and current situation
- **Intelligent Responses**: Appropriate tone and content for situation
- **Action Orientation**: Focuses on actionable insights and next steps

### Message Types
- **Status Requests**: "How are my goals?" → Comprehensive status with priorities
- **Check-ins**: "Walked the dog" → Acknowledgment and encouragement  
- **Alerts**: Proactive beemergency and deadline notifications
- **Guidance**: Strategic advice based on current constraints and priorities

## Technical Specifications

### Message Processing
- **Queue Management**: Priority-based message processing
- **Response Generation**: Template-based → Smart → Enhanced (based on budget)
- **Delivery Guarantees**: Reliable SMS delivery with retry logic
- **Error Handling**: Graceful degradation and user notification

### Integration Patterns
- **MCP Architecture**: Modular data source integration
- **API Management**: Rate limiting and credential rotation
- **Cost Optimization**: Intelligent feature selection based on budget
- **Security**: Secure credential management and access control

*This document is actively maintained and represents the current architectural vision. For implementation details, see `docs/DEPLOYMENT.md` and `docs/OPERATIONS.md`.*