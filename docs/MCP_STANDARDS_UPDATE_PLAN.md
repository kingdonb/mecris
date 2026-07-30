# MCP Server Standards Update Plan (as of 2025-07-28)

## Executive Summary

The current Mecris MCP server (`mcp_server.py`) implements a **FastMCP-based server** with **FastAPI HTTP bridge** and **stdio transport**. This document outlines the plan to bring it up to the **MCP Specification 2025-06-18 (v1.26.0+)** standards.

**Current State**: 
- Transport: stdio + FastAPI HTTP bridge (port 8080)
- Auth: Pocket ID OIDC (multi-tenant) + standalone fallback
- Transports: stdio (for Pi/Claude) + HTTP (for Android)
- Auth: Pocket ID OIDC with JWT validation

---

## Current Implementation vs. MCP 2025-06-18 Spec

### ✅ Already Compliant

| Feature | Status | Notes |
|---------|--------|-------|
| **Protocol Version** | ✅ | Uses `InitializeRequest/Result` with `protocolVersion` |
| **Tools** | ✅ | 20+ tools via `@mcp.tool()` decorator |
| **Resources** | ⚠️ Partial | No resource implementation yet |
| **Prompts** | ⚠️ Partial | No prompt templates yet |
| **Tools** | ✅ | 20+ tools registered via `@mcp.tool()` |
| **Stdio Transport** | ✅ | `mcp_stdio_server.py` + `mcp.run_stdio_async()` |
| **HTTP Bridge** | ✅ | FastAPI on :8080 for Android |
| **Initialization** | ✅ | `InitializeRequest/Result` with capabilities |
| **Ping/Pong** | ✅ | `PingRequest` handled |
| **Tools Capability** | ✅ | `ToolsCapability` in `ServerCapabilities` |
| **Auth** | ✅ | Pocket ID OIDC + standalone fallback |
| **Notifications** | ⚠️ Partial | Resource updates, tool list changes not implemented |

### ❌ Gaps to Address

| Feature | Spec Requirement | Current State |
|---------|------------------|---------------|
| **Resources** | `ResourcesCapability` + `Resource` types | Not implemented |
| **Prompts** | `PromptsCapability` + prompt templates | Not implemented |
| **Resource Templates** | URI templates with variables | Not implemented |
| **Resource Subscriptions** | `subscribe/unsubscribe` notifications | Not implemented |
| **Elicitation** | `CreateMessageRequest` with `elicitation` | Not implemented |
| **Roots** | `RootsCapability` for workspace roots | Not implemented |
| **Sampling** | `SamplingCapability` for LLM sampling | Not implemented |
| **Progress Notifications** | `ProgressNotification` for long ops | Not implemented |
| **Tool Annotations** | `ToolAnnotations` for UX hints | Not implemented |
| **Structured Tool Output** | `ToolResultContent` structured types | Partial |
| **Resource Templates** | URI templates with variables | Not implemented |
| **Streamable HTTP** | New transport (replaces SSE) | Not implemented |
| **OAuth 2.1 / DPoP** | Token binding, DPoP proof | Pocket ID only |

---

## Architecture Assessment

### Current Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                     mcp_server.py                               │
├─────────────────────────────────────────────────────────────────┤
│  FastMCP (Tools)  +  FastAPI (HTTP Bridge)  +  Scheduler       │
├─────────────────────────────────────────────────────────────────┤
│  Transports: stdio (Pi/Claude) + HTTP :8080 (Android)          │
├─────────────────────────────────────────────────────────────────┤
│  Auth: Pocket ID OIDC (multi-tenant) + standalone fallback     │
├─────────────────────────────────────────────────────────────────┤
│  Storage: Neon Postgres (multi-tenant)                         │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended Architecture (MCP 2025-06-18)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Mecris MCP Server                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   stdio     │  │  Streamable │  │   SSE (dep) │  Transports │
│  │  Transport  │  │   HTTP      │  │  (deprecated)│             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│         └────────────────┼────────────────┘                     │
│                          ▼                                     │
│         ┌─────────────────────────────────────┐               │
│         │        MCP Protocol Core            │               │
│         │  (Initialize, Tools, Resources,     │               │
│         │   Prompts, Sampling, Roots,         │               │
│         │   Elicitation, Notifications)       │               │
│         └────────────────┬────────────────────┘               │
│                          │                                     │
│         ┌────────────────┼────────────────────┐               │
│         ▼                ▼                    ▼                │
│  ┌─────────────┐  ┌─────────────┐    ┌─────────────┐          │
│  │  Resources  │  │  Prompts    │    │  Sampling   │          │
│  │  Manager    │  │  Manager    │    │  Manager    │          │
│  └─────────────┘  └─────────────┘    └─────────────┘          │
│  ┌─────────────┐  ┌─────────────┐    ┌─────────────┐          │
│  │  Tools      │  │  Auth       │    │  Notifications│         │
│  │  Registry   │  │  Manager    │    │  Dispatcher │          │
│  └─────────────┘  └─────────────┘    └─────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Core Protocol Compliance (Week 1-2)

#### 1.1 Add Resources Capability
```python
# New: services/resource_manager.py
class ResourceManager:
    """Manages MCP Resources per spec."""
    
    async def list_resources(self) -> ListResourcesResult:
        """ListResourcesRequest -> ListResourcesResult"""
        
    async def read_resource(self, uri: str) -> ReadResourceResult:
        """ReadResourceRequest -> ReadResourceResult"""
        
    async def subscribe(self, uri: str) -> None:
        """SubscribeRequest -> subscribe to resource updates"""
        
    async def unsubscribe(self, uri: str) -> None:
        """UnsubscribeRequest"""
```

**Resources to expose:**
- `mecris://walk/{date}` - Walk data for date
- `mecris://language/{lang}` - Language stats
- `mecris://budget` - Budget status
- `mecris://health/{date}` - Health data
- `mecris://aggregate` - Aggregate status

#### 1.2 Add Prompts Capability
```python
# New: services/prompt_manager.py
class PromptManager:
    """Manages MCP Prompt templates."""
    
    async def list_prompts(self) -> ListPromptsResult:
        """List available prompt templates."""
        
    async def get_prompt(self, name: str, args: dict) -> GetPromptResult:
        """Render prompt template with arguments."""
```

**Prompts to implement:**
- `daily_briefing` - Morning briefing with walk, budget, language status
- `evening_review` - Evening review with nag suggestions
- `language_plan` - Language study plan based on pump status
- `walk_recommendation` - Weather-aware walk recommendation

#### 1.3 Add Resource Subscriptions
```python
# In server session handling
async def handle_subscribe(self, request: SubscribeRequest) -> SubscribeResult:
    """Subscribe to resource URI changes."""
    
async def handle_unsubscribe(self, request: UnsubscribeRequest) -> UnsubscribeResult:
    """Unsubscribe from resource changes."""
```

#### 1.4 Add Progress Notifications
```python
# For long-running operations (cloud sync, language sync)
async def notify_progress(self, token: str, progress: float, total: Optional[float]) -> None:
    """Send ProgressNotification to client."""
```

---

### Phase 2: Transport Modernization (Week 3)

#### 2.1 Implement Streamable HTTP Transport
```python
# New: server/streamable_http.py
from mcp.server.streamable_http import StreamableHTTPServerTransport

class MecrisStreamableTransport(StreamableHTTPServerTransport):
    """Mecris-specific Streamable HTTP transport with auth."""
    
    async def handle_request(self, request: Request) -> Response:
        # Extract auth from Authorization header
        # Validate token via Pocket ID
        # Forward to MCP core
```

**Replace SSE with Streamable HTTP** (per 2025-06-18 spec)

#### 2.2 Transport Matrix
| Transport | Status | Use Case |
|-----------|--------|----------|
| stdio | ✅ Keep | Pi, Claude CLI |
| Streamable HTTP | 🔴 Add | Android, Web, Public API |
| SSE | ⚠️ Deprecate | Legacy only |
| stdio (stdio_server.py) | ✅ Keep | Pi/Claude CLI |

---

### Phase 3: Advanced Capabilities (Week 5-6)

#### 3.1 Sampling Capability (for AI-assisted features)
```python
class SamplingManager:
    """Handle CreateMessageRequest for LLM sampling."""
    
    async def sample(self, request: CreateMessageRequest) -> CreateMessageResult:
        # Delegate to local LLM or cloud provider
        # Support structured output via ToolUseContent
```

#### 3.2 Roots Capability (Workspace awareness)
```python
class RootsManager:
    async def list_roots(self) -> ListRootsResult:
        """Return workspace roots for context."""
```

#### 3.3 Elicitation Support
```python
async def handle_elicitation(self, request: CreateMessageRequest) -> CreateMessageResult:
    """Handle elicitation requests from client."""
```

---

## Authentication & Multi-Tenancy

### Current: Pocket ID OIDC
- ✅ Working with Pocket ID
- ✅ Multi-tenant via `sub` claim
- ✅ JWT validation with JWKS
- ⚠️ No DPoP token binding

### Target: MCP OAuth 2.1 + DPoP
```python
# New: auth/mcp_oauth.py
class MCPOAuthManager:
    """MCP 2025 OAuth 2.1 + DPoP implementation."""
    
    async def validate_dpop_proof(self, dpop_header: str, token: str) -> bool:
        """Validate DPoP proof per RFC 9449."""
        
    async def issue_access_token(self, client_id: str, scope: str) -> TokenResponse:
        """Issue DPoP-bound access token."""
```

---

## Deployment Architecture

### Current
```
┌─────────────┐     ┌─────────────┐
│   Pi/CLI    │────▶│  stdio      │
└─────────────┘     └─────────────┘
                    │
                    ▼
              ┌─────────────┐
              │  mcp_server │
              │   (stdio)   │
              └─────────────┘
                    │
                    ▼
              ┌─────────────┐
              │   Neon PG   │
              └─────────────┘
```

### Target Deployment (Multi-Transport)

```
                    ┌─────────────────────┐
                    │   Load Balancer     │
                    │   (Cloudflare)      │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
       │  Home Server│  │  Fly.io     │  │  Fermyon    │
       │  (stdio)    │  │  (Streamable│  │  (SpinKube) │
       │             │  │   HTTP)     │  │             │
       └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
              │                │                │
              └────────────────┼────────────────┘
                               ▼
                        ┌─────────────┐
                        │  Neon PG    │
                        │  (shared)   │
                        └─────────────┘
```

---

## Implementation Checklist

### Phase 1: Core Compliance (Week 1-2)
- [ ] Add `ResourcesCapability` + `ResourceManager`
- [ ] Add `PromptsCapability` + `PromptManager`  
- [ ] Implement `Resource` types for all data
- [ ] Add `Subscribe/Unsubscribe` handlers
- [ ] Add `ProgressNotification` for long ops
- [ ] Add `ResourceUpdatedNotification` for live updates

### Phase 2: Transport (Week 3)
- [ ] Implement `StreamableHTTPServerTransport`
- [ ] Replace SSE endpoint with Streamable HTTP
- [ ] Add transport detection/negotiation
- [ ] Keep stdio for Pi/Claude CLI

### Phase 3: Advanced (Week 3-4)
- [ ] Add `SamplingCapability` + `SamplingManager`
- [ ] Add `RootsCapability` + `RootsManager`
- [ ] Add `Elicitation` support
- [ ] Add `ToolAnnotations` to all tools

### Phase 4: Auth & Multi-tenancy
- [ ] DPoP token binding
- [ ] MCP OAuth 2.1 authorization server
- [ ] Device-bound tokens for Android

### Phase 5: Deployment
- [ ] Fly.io deployment config
- [ ] Cloudflare Load Balancer + TLS
- [ ] SpinKube on Fly.io (backup)
- [ ] Fermyon Cloud (backup)
- [ ] Health checks + graceful shutdown

---

## Testing Strategy

### Unit Tests
```python
# tests/test_mcp_resources.py
async def test_list_resources():
    result = await resource_manager.list_resources()
    assert len(result.resources) > 0
    
async def test_read_resource():
    result = await resource_manager.read_resource("mecris://walk/2025-07-28")
    assert result.contents[0].uri == "mecris://walk/2025-07-28"

async def test_subscribe_resource():
    await resource_manager.subscribe("mecris://walk/2025-07-28")
    # Verify notification on update
```

### Integration Tests
```python
# tests/test_mcp_integration.py
async def test_full_initialize_flow():
    async with stdio_client() as (read, write):
        session = ClientSession(read, write)
        result = await session.initialize()
        assert result.protocol_version == "2025-06-18"
        assert result.capabilities.tools is not None
        assert result.capabilities.resources is not None
```

### Transport Tests
```python
async def test_streamable_http_transport():
    async with streamable_http_client(url) as (read, write):
        session = ClientSession(read, write)
        await session.initialize()
        tools = await session.list_tools()
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Resource subscription complexity | High | Medium | Start with polling fallback |
| Streamable HTTP adoption | Medium | High | Keep SSE as fallback |
| DPoP implementation | Medium | High | Use established library |
| Neon connection pooling | Low | High | PgBouncer + read replicas |
| Android mesh + MCP | High | High | Feature flags, gradual rollout |

---

## File Structure (Target)

```
mecris/
├── mcp_server.py              # Main entry (stdio + HTTP)
├── mcp_stdio_server.py        # Stdio entry point
├── server/
│   ├── __init__.py
│   ├── transports/
│   │   ├── __init__.py
│   │   ├── stdio_transport.py
│   │   ├── streamable_http.py
│   │   └── sse_transport.py (deprecated)
│   ├── protocol/
│   │   ├── __init__.py
│   │   ├── resources.py
│   │   ├── prompts.py
│   │   ├── sampling.py
│   │   ├── roots.py
│   │   ├── elicitation.py
│   │   └── notifications.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── mcp_oauth.py
│   │   └── pocket_id.py
│   └── services/
│       ├── resource_manager.py
│       ├── prompt_manager.py
│       ├── sampling_manager.py
│       └── roots_manager.py
├── mcp_server.py              # Main entry
├── mcp_stdio_server.py        # Stdio entry
├── services/                  # Existing services
└── tests/
    ├── test_mcp_resources.py
    ├── test_mcp_prompts.py
    ├── test_mcp_transports.py
    └── test_mcp_integration.py
```

---

## Migration Strategy

### Branch Strategy
```
main (current stable)
  └── feature/mcp-2025-update
      ├── Phase 1: Core compliance
      ├── Phase 2: Transport
      ├── Phase 3: Advanced capabilities
      └── main (merge after validation)
```

### Validation Gates
1. **Protocol Tests**: All MCP protocol tests pass
2. **Transport Tests**: stdio + Streamable HTTP both work
3. **Android Integration**: App connects to all transports
4. **Load Test**: 100 concurrent sessions
5. **Chaos**: Kill endpoints, verify failover

---

## Appendix: MCP Spec References

- **MCP Spec 2025-06-18**: https://github.com/modelcontextprotocol/specification
- **Python SDK 1.26.0**: https://github.com/modelcontextprotocol/python-sdk
- **Transport Spec**: Streamable HTTP Transport (replaces SSE)
- **Auth**: OAuth 2.1 + DPoP (RFC 9449)

---

*Document Version: 1.0*  
*Author: Mecris Team*  
*Date: 2025-07-28*