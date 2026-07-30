# MCP Server Standards Update Plan (as of 2025-11-25 spec)

## Executive Summary

**Current State**: Mecris MCP server (`mcp_server.py`) implements a **FastMCP-based server** with **stdio + FastAPI HTTP bridge** and **Pocket ID auth**. It has tools working but lacks Resources, Prompts, Subscriptions, and several 2025-11-25 spec features.

**Current State**:
- Transport: stdio (for Pi/Claude) + FastAPI HTTP bridge (port 8080) for Android
- Auth: Pocket ID OIDC (multi-tenant) + standalone fallback
- Tools: 20+ tools working via `@mcp.tool()`
- Auth: Pocket ID OIDC with JWT validation + standalone fallback
- Transport: stdio (for Pi/Claude) + HTTP (port 8080) for Android

**Target State**: Full MCP 2025-11-25 spec compliance with Streamable HTTP transport, Resources, Prompts, Subscriptions, Elicitation, Roots, Sampling, Tasks, and DPoP auth.

---

## Current State vs. MCP 2025-11-25 Spec

### ✅ Already Compliant

| Feature | Status | Notes |
|---------|--------|-------|
| **Protocol Version** | ✅ | Uses `InitializeRequest/Result` with `protocolVersion` |
| **Tools** | ✅ | 20+ tools via `@mcp.tool()` decorator |
| **Stdio Transport** | ✅ | `mcp_stdio_server.py` + `mcp.run_stdio_async()` |
| **HTTP Bridge** | ✅ | FastAPI on :8080 for Android |
| **Initialization** | ⚠️ Partial | `InitializeRequest/Result` with capabilities |
| **Ping/Pong** | ✅ | `PingRequest` handled |
| **Tools Capability** | ✅ | `ToolsCapability` in `ServerCapabilities` |
| **Auth** | ✅ | Pocket ID OIDC with JWT validation + standalone fallback |

### ❌ Gaps to Address (MCP 2025-11-25)

| Feature | Spec Requirement | Current State |
|---------|------------------|---------------|
| **Resources** | `ResourcesCapability` + `Resource` types | Not implemented |
| **Prompts** | `PromptsCapability` + prompt templates | Not implemented |
| **Resource Subscriptions** | `subscribe/unsubscribe` + `ResourceUpdatedNotification` | Not implemented |
| **Prompts Capability** | `PromptsCapability` + `Prompt` types | Not implemented |
| **Elicitation** | `ElicitationCapability` + `ElicitRequest`/`ElicitResult` | Not implemented |
| **Roots** | `RootsCapability` for workspace awareness | Not implemented |
| **Sampling** | `SamplingCapability` for LLM sampling | Not implemented |
| **Tasks** | `TasksCapability` for long-running ops | Not implemented |
| **Elicitation** | `ElicitationCapability` + `ElicitRequest`/`ElicitResult` | Not implemented |
| **Roots** | `RootsCapability` for workspace awareness | Not implemented |
| **Sampling** | `SamplingCapability` for LLM sampling | Not implemented |
| **Tasks** | `TasksCapability` for long-running ops | Not implemented |
| **Streamable HTTP Transport** | New transport (replaces SSE) | Not implemented |
| **Server Discovery** | `server/discover` RPC | Not implemented |
| **Per-request Capabilities** | Client capabilities per-request in `_meta` | Not implemented |
| **Per-request Version** | Protocol version in header + `_meta` | Not implemented |
| **Elicitation** | `ElicitRequest`/`ElicitResult` | Not implemented |
| **Roots** | `RootsCapability` for workspace awareness | Not implemented |
| **Sampling** | `SamplingCapability` for LLM sampling | Not implemented |
| **Tasks** | `TasksCapability` for long-running ops | Not implemented |
| **Streamable HTTP Transport** | New transport (replaces SSE) | Not implemented |
| **Server Discovery** | `server/discover` RPC | Not implemented |
| **Per-request Capabilities** | Client capabilities per-request in `_meta` | Not implemented |
| **Per-request Version** | Protocol version in header + `_meta` | Not implemented |
| **DPoP Token Binding** | RFC 9449 token binding | Not implemented |
| **OAuth 2.1 Auth** | MCP OAuth 2.1 authorization server | Pocket ID only |

---

## Architecture Assessment

### Current Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                     mcp_server.py                               │
├─────────────────────────────────────────────────────────────────┤
│  FastMCP (Tools)  +  FastAPI (HTTP Bridge)  +  Scheduler       │
├─────────────────────────────────────────────────────────────────┤
│  Transport: stdio (Pi/Claude) + HTTP :8080 (Android)           │
├─────────────────────────────────────────────────────────────────┤
│  Auth: Pocket ID OIDC (multi-tenant) + standalone fallback     │
├─────────────────────────────────────────────────────────────────┤
│  Storage: Neon Postgres (multi-tenant)                         │
└─────────────────────────────────────────────────────────────────┘
```

### Target Architecture (MCP 2025-11-25)

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
│         ┌─────────────────────────────────┐                   │
│         │        MCP Protocol Core        │                   │
│         │  (Initialize, Tools, Resources, │                   │
│         │   Prompts, Sampling, Roots,     │                   │
│         │   Elicitation, Notifications)   │                   │
│         └────────────────┬────────────────┘                   │
│                          │                                     │
│         ┌────────────────┼────────────────────┐               │
│         ▼                ▼                    ▼                │
│  ┌─────────────┐  ┌─────────────┐    ┌─────────────┐          │
│  │  Resources  │  │  Prompts    │    │  Sampling   │          │
│  │  Manager    │  │  Manager    │    │  Manager    │          │
│  └─────────────┘  └─────────────┘    └─────────────┘          │
│  ┌─────────────┐  ┌─────────────┐    ┌─────────────┐          │
│  │  Prompts    │  │  Roots      │    │  Sampling   │          │
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

### Phase 1: Core Compliance (Week 1-2)

#### 1.1 Add Resources Capability
```python
# New: services/resource_manager.py
class ResourceManager:
    """Manages MCP Resources per 2025-11-25 spec."""
    
    async def list_resources(self) -> ListResourcesResult:
        """ListResourcesRequest -> ListResourcesResult"""
        
    async def read_resource(self, uri: str) -> ReadResourceResult:
        """ReadResourceRequest -> ReadResourceResult"""
        
    async def list_resource_templates(self) -> ListResourceTemplatesResult:
        """ListResourceTemplatesRequest -> ListResourceTemplatesResult"""
        
    async def subscribe(self, uri: str) -> None:
        """Subscribe to resource changes."""
        
    async def unsubscribe(self, uri: str) -> None:
        """Unsubscribe from resource changes."""
        
    async def notify_resource_changed(self, uri: str):
        """Send ResourceUpdatedNotification to subscribers."""

# Resources to expose:
# - mecris://walk/{date} - Walk data for date
# - mecris://walk/today - Today's walk data
# - mecris://language/{lang} - Language stats
# - mecris://language/all - All languages
# - mecris://budget - Budget status
# - mecris://health/{date} - Health data
# - mecris://aggregate - Aggregate status
# - mecris://narrator/context - Full narrator context
```

#### 1.2 Add Prompts Capability
```python
# New: services/prompt_manager.py
class PromptManager:
    """Manages MCP Prompts per 2025-11-25 spec."""
    
    async def list_prompts(self) -> ListPromptsResult:
        """ListPromptsRequest -> ListPromptsResult"""
        
    async def get_prompt(self, name: str, args: Dict[str, str]) -> GetPromptResult:
        """GetPromptRequest -> GetPromptResult"""

# Prompts to implement:
# - daily_briefing(date?, tone?, include_weather?)
# - evening_review(date?, tone?)
# - language_plan(language, days?, intensity?)
# - walk_recommendation(lat, lon, preference?)
# - weekly_review(week_start?)
# - nag_response(nag_type, context, tone?)
```

#### 1.3 Add Resource Subscriptions
```python
# New: services/resource_subscription_manager.py
class ResourceSubscriptionManager:
    """Manages resource subscriptions per 2025-11-25 spec."""
    
    async def subscribe(self, uri: str, client_id: str) -> bool:
        """Subscribe a client to resource changes."""
        
    def unsubscribe(self, uri: str, client_id: str) -> bool:
        """Unsubscribe a client from resource changes."""
        
    async def notify_resource_changed(self, uri: str):
        """Send ResourceUpdatedNotification to all subscribers."""
```

#### 1.4 Add Progress Notifications
```python
# In resource_manager.py / prompt_manager.py
async def notify_progress(self, progress_token: str, progress: float, total: Optional[float] = None):
    """Send ProgressNotification to client."""
```

#### 1.5 Add Tool Annotations
```python
# Update all @mcp.tool() decorators to include annotations
@mcp.tool(
    annotations=ToolAnnotations(
        title="Sync Walk Data",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )
)
async def upload_walk(...):
    ...
```

---

### Phase 2: Transport Modernization (Week 3)

#### 2.1 Implement Streamable HTTP Transport
```python
# New: server/transports/streamable_http.py
from mcp.server.streamable_http import StreamableHTTPServerTransport

class MecrisStreamableTransport(StreamableHTTPServerTransport):
    """Mecris-specific Streamable HTTP transport with auth."""
    
    async def handle_request(self, request: Request) -> Response:
        # Extract auth from Authorization header
        # Validate token via Pocket ID
        # Forward to MCP core
```

#### 2.2 Replace SSE with Streamable HTTP
```python
# In mcp_server.py
# Replace SSE endpoint with Streamable HTTP
# Keep stdio transport for Pi/Claude
# Run both in same event loop via asyncio.gather()
```

#### 2.3 Transport Matrix
| Transport | Status | Use Case |
|-----------|--------|----------|
| stdio | ✅ Keep | Pi, Claude CLI |
| Streamable HTTP | 🔴 Add | Android, Web, Public API |
| SSE | ⚠️ Deprecate | Legacy only |

---

### Phase 3: Advanced Capabilities (Week 3-4)

#### 3.1 Add Server Discovery
```python
# New: mcp_server.py - add server/discover RPC
@mcp.tool(name="server/discover", description="Discover server capabilities")
async def discover_server() -> DiscoverResult:
    return DiscoverResult(
        supportedVersions=["2025-11-25", "2025-06-18"],
        capabilities=ServerCapabilities(...),
        serverInfo=Implementation(name="mecris", version="0.0.1"),
        instructions="Mecris personal accountability server..."
    )
```

#### 3.2 Per-Request Capabilities & Version
```python
# In mcp_server.py - update get_authorized_user to extract _meta
async def get_authorized_user(
    user_id: Optional[str] = Depends(get_current_user),
    protocol_version: str = Header(..., alias="MCP-Protocol-Version"),
    client_info: Implementation = Body(..., alias="io.modelcontextprotocol/clientInfo"),
    client_capabilities: ClientCapabilities = Body(..., alias="io.modelcontextprotocol/clientCapabilities"),
    log_level: Optional[LoggingLevel] = Body(None, alias="io.modelcontextprotocol/logLevel"),
):
    # Validate protocol version matches header
    # Store client_info and client_capabilities for this request
    # Return user_id
```

#### 3.3 Add Server Discovery Endpoint
```python
@app.post("/server/discover")
async def discover_server() -> DiscoverResult:
    return DiscoverResult(
        supportedVersions=["2025-11-25", "2025-06-18"],
        capabilities=ServerCapabilities(...),
        serverInfo=Implementation(name="mecris", version="0.0.1"),
        instructions="Mecris personal accountability server..."
    )
```

#### 3.4 Per-Request Client Capabilities
```python
# Update get_authorized_user to extract and validate per-request capabilities
# Store in request.state for use by tool handlers
```

---

### Phase 3: Advanced Capabilities (Week 5-6)

#### 3.1 Add Elicitation Capability
```python
# New: services/elicitation_manager.py
class ElicitationManager:
    """Handle server-to-client elicitation requests."""
    
    async def elicit(self, request: ElicitRequest) -> ElicitResult:
        """Handle elicitation/create request from server."""
```

#### 3.2 Add Roots Capability
```python
# New: services/roots_manager.py
class RootsManager:
    """Manage workspace roots per SEP-2322."""
    
    async def list_roots(self) -> ListRootsResult:
        """ListRootsRequest -> ListRootsResult"""
        
    async def subscribe_roots(self, client_id: str) -> None:
        """Subscribe to root changes."""
```

#### 3.3 Add Sampling Capability
```python
# New: services/sampling_manager.py
class SamplingManager:
    """Handle LLM sampling requests from server."""
    
    async def sample(self, request: CreateMessageRequest) -> CreateMessageResult:
        """Handle sampling/createMessage request."""
```

#### 3.4 Add Tasks Capability
```python
# New: services/task_manager.py
class TaskManager:
    """Manage long-running tasks per SEP-1686."""
    
    async def create_task(self, request: CreateTaskRequest) -> CreateTaskResult:
        """Create a new background task."""
        
    async def get_task(self, task_id: str) -> Task:
        """Get task status and result."""
        
    async def cancel_task(self, task_id: str) -> CancelTaskResult:
        """Cancel a running task."""
        
    async def list_tasks(self) -> ListTasksResult:
        """List all tasks for the current user."""
```

---

### Phase 4: Auth & Multi-tenancy (Week 7-8)

#### 4.1 DPoP Token Binding (RFC 9449)
```python
# New: services/auth/dpop.py
class DPoPManager:
    """DPoP token binding per RFC 9449."""
    
    async def validate_dpop_proof(self, dpop_header: str, token: str) -> bool:
        """Validate DPoP proof."""
        
    async def create_dpop_proof(self, token: str, method: str, url: str) -> str:
        """Generate DPoP proof for request."""
```

#### 4.2 MCP OAuth 2.1 Authorization Server
```python
# New: auth/mcp_oauth.py
class MCPOAuthServer:
    """MCP OAuth 2.1 authorization server per spec."""
    
    async def authorize(self, request: AuthorizationRequest) -> AuthorizationResponse:
        """Handle authorization request."""
        
    async def token(self, request: TokenRequest) -> TokenResponse:
        """Issue access tokens."""
        
    async def revoke(self, request: RevokeRequest) -> RevokeResponse:
        """Revoke tokens."""
```

#### 4.2 Device-bound Tokens for Android
```python
# In PocketIdAuth - add device binding
# Generate DPoP keys on first auth, store in Android Keystore
# Include DPoP proof in all API requests
```

---

### Phase 5: Deployment (Week 9-10)

#### 5.1 Fly.io Deployment
```toml
# fly.toml
app = "mecris-api"
primary_region = "iad"

[build]
  image = "ghcr.io/kingdonb/mecris-api:latest"

[env]
  MECRIS_MODE = "multi-tenant"
  NEON_DB_URL = "${NEON_DB_URL}"
  POCKET_ID_URL = "https://auth.mecris.dev"

[services]
  internal_port = 8080
  protocol = "tcp"
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1
```

#### 5.2 Cloudflare Load Balancer
```yaml
# Cloudflare Load Balancer config
origin_pools:
  - name: fly-primary
    origins:
      - address: mecris-api.fly.dev
        weight: 1
    health_check: /health

  - name: fermyon-backup
    origins:
      - address: mecris-spin.fermyon.app
        weight: 1
    health_check: /health
```

#### 5.3 SpinKube on Fly.io
```yaml
# spin-deploy.yaml
apiVersion: core.spinoperator.dev/v1alpha1
kind: SpinApp
metadata:
  name: mecris-spin
spec:
  image: ghcr.io/kingdonb/mecris-spin:latest
  replicas: 2
  executor: spin
  trigger:
    http:
      port: 8080
```

---

## Testing Strategy

### Unit Tests
```python
# tests/test_mcp_resources.py
async def test_list_resources():
    result = await resource_manager.list_resources()
    assert len(result.resources) > 0
    
async def test_read_resource():
    result = await resource_manager.read_resource("mecris://walk/today")
    assert result.contents[0].uri == "mecris://walk/today"

async def test_subscribe_resource():
    await resource_manager.subscribe("mecris://walk/today", "client-1")
    # Verify notification on update

# tests/test_mcp_prompts.py
async def test_list_prompts():
    result = await prompt_manager.list_prompts()
    assert len(result.prompts) >= 6

async def test_get_prompt():
    result = await prompt_manager.get_prompt("morning_briefing", {"date": "2025-07-30"})
    assert len(result.messages) == 1
```

### Integration Tests
```python
# tests/test_mcp_integration.py
async def test_full_initialize_flow():
    async with stdio_client() as (read, write):
        session = ClientSession(read, write)
        result = await session.initialize()
        assert result.protocol_version == "2025-11-25"
        assert result.capabilities.tools is not None
        assert result.capabilities.resources is not None
        assert result.capabilities.prompts is not None

async def test_streamable_http_transport():
    async with streamable_http_client() as (read, write):
        session = ClientSession(read, write)
        await session.initialize()
        tools = await session.list_tools()
```

### Transport Tests
```python
async def test_streamable_http_transport():
    async with streamable_http_client() as (read, write):
        session = ClientSession(read, write)
        await session.initialize()
        tools = await session.list_tools()
        
async def test_stdio_transport():
    async with stdio_client() as (read, write):
        session = ClientSession(read, write)
        await session.initialize()
        tools = await session.list_tools()
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] Pocket ID public DNS + TLS (`auth.mecris.dev`)
- [ ] API Gateway deployed (Fly.io + Cloudflare)
- [ ] SpinKube cluster deployed
- [ ] Android rebuild with mesh client
- [ ] Load test: 1000 concurrent users
- [ ] Chaos engineering: kill endpoints, verify failover

### Launch Sequence
1. **Staging**: Deploy to staging, run E2E tests
2. **Canary**: 5% traffic to new cloud API
3. **Rollout**: 100% to cloud, home server as fallback
4. **Android**: Roll out mesh client via Play Store (staged rollout)

### Rollback Plan
- DNS failback to home server in < 60s
- Android app falls back to local-only mode
- Database unchanged (shared Neon)

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
│   │   ├── pocket_id.py
│   │   ├── mcp_oauth.py
│   │   └── dpop.py
│   └── services/
│       ├── resource_manager.py
│       ├── prompt_manager.py
│       ├── sampling_manager.py
│       ├── roots_manager.py
│       ├── elicitation_manager.py
│       └── task_manager.py
├── mcp_server.py              # Main entry
├── mcp_stdio_server.py        # Stdio entry
├── services/                  # Existing services
├── docs/
│   ├── MCP_STANDARDS_UPDATE_PLAN.md
│   ├── CLOUD_DEPLOYMENT_PLAN.md
│   └── ANDROID_MESH_CLIENT.md
└── tests/
    ├── test_mcp_resources.py
    ├── test_mcp_prompts.py
    ├── test_mcp_transports.py
    └── test_mcp_integration.py
```

---

## Appendix: Key Spec References

- **MCP Spec 2025-11-25**: https://github.com/modelcontextprotocol/specification/tree/main/specification/2025-11-25
- **Schema**: https://github.com/modelcontextprotocol/specification/blob/main/schema/2025-11-25/schema.ts
- **Transport Spec**: Streamable HTTP Transport (replaces SSE)
- **Auth**: OAuth 2.1 + DPoP (RFC 9449)
- **SEP-2567**: Sessionless MCP via Explicit State Handles
- **SEP-2575**: Make MCP Stateless
- **SEP-2567**: Sessionless MCP via Explicit State Handles
- **SEP-2575**: Make MCP Stateless
- **SEP-2322**: MRTR (Multi-Round-Trip Requests)
- **SEP-2549**: TTL for List Results
- **SEP-2322**: MRTR (Multi-Round-Trip Requests)
- **SEP-2549**: TTL for List Results
- **SEP-2322**: MRTR (Multi-Round-Trip Requests)

---

*Document Version: 1.0*  
*Author: Mecris Team*  
*Date: 2025-07-30*  
*Target Spec: MCP 2025-11-25 (latest as of 2025-07-28)*