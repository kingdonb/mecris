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

The architecture follows a **Peer Persistence** model. Both the Local Host (Python MCP) and the Cloud Hub (WASM API) maintain direct lines to the central Neon database, ensuring the system can survive a total loss of the cloud APIs.

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
         │ MOBILE GO  │  │ AGENTS/BOTS │  │ HUMAN / CLI   │  │ CI TRIGGERS │
         │ (Sensors)  │  │ (Narrators) │  │ (Gemini/Term) │  │ (GHA/Hooks) │
         └────────────┘  └─────────────┘  └───────────────┘  └─────────────┘
```

## Core Components

### The Hub Layer (Persistence & Logic)
- **Local Host (Python MCP)**: The primary peer for human interaction. It bridges local data (Obsidian vault, filesystem) and handles direct database operations for the narrator context.
- **Cloud Hub (Fermyon/Akamai)**: The high-availability failover and mobile bridge. It provides the "always-on" logic for the Android app and native crons for autonomous nagging.
- **WASM Brain**: Shared business logic (Review Pump, Budget Governor) that runs identically across both Hubs.

### The Host Layer (Sensors & Interfaces)
- **Mobile Host (Android)**: Captures high-fidelity physical data (steps, exercise) and provides the primary UI for "The Majesty Cake."
- **Narrator Interface**: Agents (Gemini, Claude) consume the "Standard Bus" via the Local MCP to provide strategic guidance.
- **CI Triggers**: External automation (GitHub Actions) pokes the Cloud Hub to force periodic reconciliation.

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
