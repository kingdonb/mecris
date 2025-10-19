# 🏗️ Mecris Architecture

*System design for autonomous SMS-based accountability system*

> **Vision**: Mecris operates as an invisible, always-available accountability partner accessible entirely through SMS conversations. Users don't know or care about the technical infrastructure - they simply text their accountability system and receive intelligent, context-aware responses.

## Overview

Mecris transforms from a Claude Code CLI tool into a production SMS accountability system that:
- Processes messages through persistent message queues
- Runs autonomously without manual intervention  
- Provides intelligent, context-aware responses
- Integrates seamlessly with personal data sources
- Operates within budget constraints through intelligent decision making

## System Architecture

```
SMS Interface → Message Queue → Mecris Core → Data Sources
     ↓              ↓              ↓             ↓
Text Messages   Async Processing  Decision Engine  Beeminder
WhatsApp        Priority Queue    Budget Tracker   Obsidian
Voice Messages  Rate Limiting     Context Memory   Usage APIs
```

## Core Components

### SMS Interface Layer
- **Twilio Integration**: SMS and WhatsApp message processing
- **Message Queue**: Asynchronous processing with priority handling
- **Conversation State**: Context preservation across interactions
- **Rate Limiting**: Intelligent throttling and escalation

### Decision Engine
- **Heuristic Processing**: Rule-based decision making without Claude API
- **Budget Awareness**: Intelligent feature degradation when budget is low
- **Context Integration**: Unified narrator context from all data sources
- **Priority Management**: Urgent vs routine message handling

### Data Integration Layer
- **Beeminder**: Goal tracking and beemergency detection
- **Usage Tracking**: Budget monitoring and API cost management
- **Obsidian**: Personal knowledge base and daily notes
- **External APIs**: Weather, calendar, and other contextual data

## Deployment Architecture

### Production Environment
- **Containerized Deployment**: Docker-based for portability
- **Ephemeral Infrastructure**: Daily EC2 instances with user_data bootstrapping
- **Stateless Design**: No persistent local storage requirements
- **Health Monitoring**: Comprehensive service monitoring and alerting

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