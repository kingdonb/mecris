# MCP Standards Update Plan — Target: 2026-07-28 Spec

**Status**: Planning only — no implementation yet  
**Current Spec**: 2025-11-25 (our codebase) → **Target Spec**: 2026-07-28 (released this week)  
**Delta**: One major version jump, biggest rewrite in MCP history (stateless)

---

## Executive Summary

The 2026-07-28 spec is a **stateless rewrite**. It removes protocol-level sessions, the `initialize` handshake, SSE transport, and three features (Roots, Sampling, Logging). It adds **Streamable HTTP**, **`server/discover`**, **per-request capabilities**, **`resultType` on all results**, **DPoP token binding**, **MRTR pattern**, and **`subscriptions/listen`**.

**Mecris gap**: We're built on 2025-11-25 patterns (FastMCP + SSE + `initialize`). The transport and handshake must change. Auth must add DPoP + `iss` validation. Resources/Prompts exist in code but aren't registered with MCP.

---

## What We Must Do (Nominal Conformance Only)

### Phase 1: Transport & Handshake (Required for any 2026-07-28 claim)

| Task | File | Effort |
|------|------|--------|
| Add `server/discover` RPC | `mcp_server.py` | Low |
| Extract per-request `_meta` (protocolVersion, clientCapabilities, clientInfo, logLevel) | `mcp_server.py` / `auth_service.py` | Medium |
| Add `resultType: "complete"` to every tool result | `mcp_server.py` (20+ tools) | Low |
| Implement **Streamable HTTP transport** (replace `mcp.sse_app()`) | New: `server/transports/streamable_http.py` | **High** |
| Keep stdio `initialize` working for Pi/Claude (transition) | `mcp_stdio_server.py` | Low |
| Remove `Mcp-Session-Id` handling (we don't use it) | N/A | None |

### Phase 2: Auth Hardening (Required by spec)

| Task | File | Effort |
|------|------|--------|
| Add **DPoP proof validation** (RFC 9449) | `services/auth_service.py` | Medium |
| Add **`iss` claim validation** per SEP-2468 | `services/auth_service.py` | Low |
| Update Android `PocketIdAuth` to send DPoP proofs | `mecris-go-project/.../PocketIdAuth.kt` | Medium |

### Phase 3: MCP Feature Registration (Already built, just wire up)

| Task | File | Effort |
|------|------|--------|
| Register `ResourceManager` with FastMCP | `mcp_server.py` | Low |
| Register `PromptManager` with FastMCP | `mcp_server.py` | Low |
| Expose pg_notify via **`subscriptions/listen`** stream | `services/walk_cache_listener.py` + new transport | Medium |
| Implement **Elicitation via MRTR** (SEP-2322) | New: `services/elicitation_manager.py` | Medium |

### Phase 4: Deferred / Optional

| Feature | Spec Status | Decision |
|---------|-------------|----------|
| **Roots** | Deprecated (SEP-2577) | **Don't implement** |
| **Sampling** | Deprecated (SEP-2577) | **Don't implement** |
| **Logging** | Deprecated (SEP-2577) | **Don't implement** (Python logging) |
| **Tasks** | Extension (`io.modelcontextprotocol/tasks`) | **Defer** — optional |
| **Elicitation** | Via MRTR (SEP-2322) | Implement in Phase 3 |

---

## Current Codebase Reality Check

| Component | 2025-11-25 Status | 2026-07-28 Work Needed |
|-----------|-------------------|------------------------|
| **Tools** | ✅ 20+ working | Add `resultType` |
| **Resources** | ✅ `resource_manager.py` exists | Register with MCP |
| **Prompts** | ✅ `prompt_manager.py` exists | Register with MCP |
| **Subscriptions** | ✅ pg_notify app-level | Expose as `subscriptions/listen` |
| **stdio Transport** | ✅ Works | Keep `initialize` for Pi |
| **HTTP Transport** | ❌ SSE (`mcp.sse_app()`) | **Rewrite to Streamable HTTP** |
| **Auth** | Pocket ID Bearer | Add DPoP + `iss` validation |
| **Handshake** | `initialize` required | Per-request `_meta` + `server/discover` |
| **Result Format** | Raw tool results | `resultType` discriminator |

---

## Transport Architecture Change

### Current (2025-11-25)
```
┌─────────────┐     ┌─────────────┐
│   stdio     │     │   SSE       │  (FastMCP built-in)
│  (Pi/Claude)│     │  (Android)  │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 ▼
          ┌─────────────┐
          │  FastMCP    │
          │  + FastAPI  │
          └─────────────┘
```

### Target (2026-07-28)
```
┌─────────────┐     ┌─────────────────────┐
│   stdio     │     │  Streamable HTTP    │  (New transport)
│  (Pi/Claude)│     │  (Android + Public) │
└──────┬──────┘     └──────────┬──────────┘
       │                       │
       └───────────┬───────────┘
                   ▼
          ┌─────────────────┐
          │  MCP Protocol   │
          │  Core (stateless)│
          │  - server/discover
          │  - per-request _meta
          │  - resultType
          │  - subscriptions/listen
          └────────┬────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
Tools         Resources        Prompts
```

---

## Implementation Order (Minimum Viable Conformance)

### Sprint 1: Transport + Handshake
1. `server/discover` RPC endpoint
2. Per-request `_meta` extraction middleware
3. `resultType: "complete"` on all tools
4. **Streamable HTTP transport** (biggest lift)
5. Keep stdio `initialize` for Pi

### Sprint 2: Auth
6. DPoP validation in `auth_service.py`
7. `iss` claim validation (SEP-2468)
8. Android DPoP client update

### Sprint 3: Feature Registration
9. Register `ResourceManager` + `PromptManager`
10. `subscriptions/listen` stream over Streamable HTTP
11. MRTR-based elicitation helper

---

## What We Explicitly WON'T Do

| Feature | Reason |
|---------|--------|
| Roots | Deprecated, no user value |
| Sampling | Deprecated, servers call LLMs directly |
| Logging | Deprecated, use stderr/OpenTelemetry |
| Tasks extension | Optional, no current use case |
| Full OAuth 2.1 AS | Pocket ID is our OIDC provider; DPoP on top is enough |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Streamable HTTP transport complexity | High | Blocks Android | Use MCP Python SDK's `StreamableHTTPServerTransport` |
| DPoP interop with Pocket ID | Medium | Auth breaks | Test against Pocket ID first; fallback to Bearer during transition |
| Pi/Claude stdio compatibility | Low | Pi breaks | Keep `initialize` working on stdio indefinitely |
| `resultType` on all tools | Low | Tedious | Script the edit (20 tools) |

---

## Dependencies

- MCP Python SDK ≥ 1.9.0 (has Streamable HTTP transport)
- Pocket ID must support `authorization_response_iss_parameter_supported: true` (SEP-2468)
- Android OkHttp DPoP interceptor

---

## Success Criteria (Nominal Conformance)

- [ ] `server/discover` returns supported versions + capabilities
- [ ] Streamable HTTP endpoint accepts requests with `Mcp-Method`, `Mcp-Name` headers
- [ ] Every request validates `protocolVersion` + `clientCapabilities` in `_meta`
- [ ] Every tool result includes `resultType: "complete"`
- [ ] DPoP proof validated on authenticated requests
- [ ] `iss` claim validated on OAuth callback
- [ ] `resources/list`, `prompts/list` work via MCP
- [ ] `subscriptions/listen` streams walk invalidation notifications
- [ ] Pi/Claude stdio still works (with `initialize`)

---

## Appendix: Spec References

| Spec | URL |
|------|-----|
| 2026-07-28 Changelog | https://github.com/modelcontextprotocol/specification/blob/main/docs/specification/2026-07-28/changelog.mdx |
| SEP-2575 (Stateless) | https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2575 |
| SEP-2567 (Sessionless) | https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2567 |
| SEP-2243 (HTTP Headers) | https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2243 |
| SEP-2322 (MRTR) | https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2322 |
| SEP-2468 (iss claim) | https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2468 |
| SEP-2577 (Deprecations) | https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2575 |
| SEP-2663 (Tasks Extension) | https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2663 |
| Streamable HTTP Spec | https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http |

---

*Plan Version: 1.0*  
*Target Spec: 2026-07-28*  
*Philosophy: Minimum nominal conformance — no polishing turds*