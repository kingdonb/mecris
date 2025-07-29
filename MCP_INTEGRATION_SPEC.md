# MCP Integration Specification

> Machine Context Provider integrations for the Mecris personal accountability system

## Overview

Mecris will integrate with multiple MCP servers to provide structured access to personal data sources. This document specifies how we'll compose existing and custom MCP capabilities into our unified FastAPI server.

## Architecture Pattern

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Claude Code   │◄──►│   Mecris MCP     │◄──►│  External MCPs  │
│   (Narrator)    │    │   Aggregator     │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                         │
                              │                         ├─ mcp-obsidian
                              ▼                         ├─ mecris-beeminder
                       ┌──────────────┐                 └─ mecris-monitor
                       │   Direct     │
                       │   Integrations│
                       └──────────────┘
                              │
                              ├─ Twilio SMS
                              └─ Time Tracker
```

Our Mecris MCP server acts as an **aggregator and adapter**, providing unified endpoints that compose data from multiple sources.

---

## 1. Obsidian Integration (External MCP)

### Source
- **Repository**: https://github.com/MarkusPfundstein/mcp-obsidian
- **Status**: ✅ Existing, mature
- **Integration Method**: MCP client connection

### Available Capabilities

| Tool | Purpose | Mecris Usage |
|------|---------|--------------|
| `list_files_in_vault` | Lists all files/dirs in vault root | Daily note discovery, content indexing |
| `list_files_in_dir` | Lists files in specific directory | Organized content browsing |
| `get_file_contents` | Returns single file content | Goal extraction, todo parsing |
| `search` | Text search across vault | Context-aware content retrieval |
| `patch_content` | Insert content relative to headings/blocks | Goal updates, progress logging |
| `append_content` | Append to new/existing files | Session summaries, action items |
| `delete_file` | Remove files/directories | Cleanup, archiving |

### Mecris Endpoint Mapping

```python
# Our unified endpoints that use mcp-obsidian internally
GET  /goals          # search("## Goals") + content parsing
GET  /todos          # search("- [ ]") + checkbox parsing  
GET  /daily/{date}   # get_file_contents("Daily Notes/{date}.md")
POST /log-session    # append_content() to session log
POST /update-goal    # patch_content() for goal modifications
```

### Configuration Requirements

```env
# mcp-obsidian server connection
OBSIDIAN_MCP_HOST=localhost
OBSIDIAN_MCP_PORT=3001
OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault
```

### Data Formats Expected

**Daily Notes**: `YYYY-MM-DD.md` format in `Daily Notes/` folder
**Goals**: Markdown files with `## Goals` sections
**Todos**: Standard markdown checkboxes `- [ ] task` and `- [x] completed`

---

## 2. Beeminder Integration (Custom MCP)

### Source
- **Repository**: mecris-beeminder (this project)
- **Status**: 🚧 To be built
- **Integration Method**: Direct FastAPI implementation

### Required Capabilities

| Tool | Purpose | Implementation |
|------|---------|----------------|
| `list_goals` | Get all active Beeminder goals | Beeminder API `/users/{user}/goals.json` |
| `get_goal_status` | Detailed goal state + derail risk | API + derail calculation logic |
| `check_emergencies` | Goals approaching derailment | Filter by `safebuf < 1` and deadlines |
| `log_datapoint` | Add progress to goal | API POST to `/users/{user}/goals/{goal}/datapoints.json` |
| `get_derail_alerts` | Critical deadline warnings | Custom urgency classification |

### Mecris Endpoint Mapping

```python
# Beeminder-specific endpoints
GET  /beeminder/status     # Overall goal portfolio health
GET  /beeminder/emergency  # Goals requiring immediate attention  
GET  /beeminder/goal/{id}  # Individual goal details
POST /beeminder/datapoint  # Log progress (with Twilio confirmation)
GET  /beeminder/alerts     # Formatted alerts for narrator context
```

### API Integration Requirements

```env
# Beeminder API credentials
BEEMINDER_USERNAME=your_username
BEEMINDER_AUTH_TOKEN=your_auth_token
BEEMINDER_API_BASE=https://www.beeminder.com/api/v1
```

### Data Structures

```python
@dataclass
class BeeminderGoal:
    slug: str
    title: str  
    current_value: float
    target_value: float
    safebuf: int          # Days until derailment
    deadline: datetime
    derail_risk: str      # "CRITICAL" | "WARNING" | "SAFE"
    
@dataclass  
class BeemergencyAlert:
    goal_slug: str
    message: str
    urgency: str         # "IMMEDIATE" | "TODAY" | "SOON"
    suggested_action: str
```

### Derailment Logic

```python
def classify_derail_risk(goal: BeeminderGoal) -> str:
    if goal.safebuf <= 0:
        return "CRITICAL"    # Derailing today/already derailed
    elif goal.safebuf == 1:
        return "WARNING"     # Derails tomorrow
    elif goal.safebuf <= 3:
        return "CAUTION"     # Derails within 3 days
    else:
        return "SAFE"
```

---

## 3. Integration Implementation Strategy

### Phase 1: Obsidian Connection
1. Set up mcp-obsidian server as separate process
2. Build MCP client in our FastAPI app
3. Implement `/goals`, `/todos`, `/daily/{date}` endpoints
4. Test with existing vault structure

### Phase 2: Beeminder MCP
1. Implement Beeminder API client
2. Build derailment risk assessment logic  
3. Create `/beeminder/*` endpoints
4. Integrate Twilio alerts for beemergencies

### Phase 3: Unified Narrator Context
1. Combine Obsidian + Beeminder data in strategic summaries
2. Build context-aware endpoint `/narrator/context`
3. Implement session logging back to Obsidian
4. Add budget/usage monitoring

### Development Order
```
1. ✅ README.md + specs (current)
2. 🚧 Basic FastAPI server structure  
3. 🚧 mcp-obsidian client integration
4. 🔄 Beeminder API + MCP implementation
5. 🔄 Twilio alert integration
6. 🔄 Unified narrator context endpoint
```

## 4. Error Handling & Resilience

- **MCP Connection Failures**: Graceful degradation, cached responses
- **API Rate Limits**: Respectful backoff, cached goal status
- **Data Format Changes**: Validation layers, clear error messages
- **Network Issues**: Timeout handling, offline mode indicators

## 5. Security Considerations

- **API Keys**: Environment variables only, never logged
- **Vault Access**: Read-only by default, explicit write permissions
- **SMS Alerts**: Rate limiting to prevent spam
- **Data Exposure**: Minimal logging of personal content

---

This specification provides the foundation for building a robust, multi-source MCP integration that maintains the Mecris philosophy: strategic insight through structured personal data access, with budget consciousness and clear boundaries.