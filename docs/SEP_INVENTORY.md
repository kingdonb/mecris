# MCP Specifications (SEPs) Inventory

**Last Updated**: 2026-07-30  
**Latest Protocol Version**: 2026-07-28 (released 2026-07-28)  
**Previous Version**: 2025-11-25  
**Previous Version**: 2025-06-18  
**Previous Version**: 2025-03-26  
**Previous Version**: 2024-11-05

---

## SEP Inventory (from `seps/` directory)

| SEP | Title | Status | Date | Reviewed? | Notes |
|-----|-------|--------|------|-----------|-------|
| 414 | OpenTelemetry trace context propagation | ? | ? | ❌ | `_meta` keys: `traceparent`, `tracestate`, `baggage` |
| 835 | Incremental scope consent via `WWW-Authenticate` | ? | ? | ❌ | |
| 837 | OAuth client credentials flow | ? | ? | ❌ | Client credentials flow in authorization |
| 973 | Expose additional metadata for implementations | ? | ? | ❌ | Icons for tools/resources/prompts |
| 985 | Align OAuth 2.0 Protected Resource Metadata with RFC 9207 | ? | ? | ❌ | |
| 986 | Specify format for tool names | ? | ? | ❌ | |
| 991 | OAuth Client ID Metadata Documents | ✅ 2025-11-25 | ? | ✅ | Client registration mechanism |
| 994 | Shared communication practices/guidelines | ? | ? | ❌ | |
| 1024 | MCP client security requirements for local server | ? | ? | ❌ | |
| 1034 | Support default values for all primitive types in elicitation | ✅ 2025-11-25 | ? | ✅ | |
| 1036 | URL mode elicitation | ✅ 2025-11-25 | ? | ✅ | Secure out-of-band interaction |
| 1046 | Support OAuth client credentials flow | ? | ? | ❌ | |
| 1302 | Formalize working groups | ? | ? | ❌ | |
| 1303 | Input validation errors as tool execution errors | ✅ 2025-11-25 | ? | ✅ | |
| 1319 | Decouple request payload from RPC methods | ✅ 2025-11-25 | ? | ✅ | |
| 1302 | Formalize working groups | ? | ? | ❌ | Duplicate? |
| 1303 | Input validation errors as tool execution errors | ✅ 2025-11-25 | ? | ✅ | |
| 1319 | Decouple request payload from RPC methods | ✅ 2025-11-25 | ? | ✅ | |
| 1330 | Elicitation enum schema improvements | ✅ 2025-11-25 | ? | ✅ | |
| 1613 | Establish JSON Schema 2020-12 as default dialect | ✅ 2025-11-25 | ? | ✅ | |
| 1686 | Experimental tasks support | ✅ 2025-11-25 | ? | ✅ | |
| 1699 | Support polling SSE streams | ✅ 2025-11-25 | ? | ✅ | |
| 1730 | SDKs tiering system | ? | ? | ❌ | |
| 1850 | PR-based SEP workflow | ? | ? | ❌ | |
| 1865 | MCP Apps (interactive UIs) | ? | ? | ❌ | |
| 1850 | PR-based SEP workflow | ? | ? | ❌ | |
| 1865 | MCP Apps | ? | ? | ❌ | Duplicate? |
| 2085 | Governance succession | ? | ? | ❌ | |
| 2106 | Loosen schema constraints | ✅ 2025-11-25 | ? | ✅ | |
| 2133 | Extensions | ? | ? | ❌ | |
| 2148 | Contributor ladder | ? | ? | ❌ | |
| 2149 | Working group charter template | ? | ? | ❌ | |
| 2164 | Resource not found error | ? | ? | ❌ | |
| 2207 | OIDC refresh token guidance | ? | ? | ❌ | |
| 2243 | HTTP Standardization for Streamable HTTP | ✅ 2026-02-04 | ✅ | ✅ | **READ** - HTTP headers for Streamable HTTP |
| 2260 | Require Server requests to be associated with Client requests | ? | ? | ❌ | |
| 2322 | MRTR (Multi Round-Trip Requests) | ✅ 2026-07-28 | ✅ | ✅ | **READ** - MRTR pattern |
| 2468 | Recommend issuer claim for auth | ✅ 2026-07-28 | ? | ✅ | |
| 2484 | Conformance tests required for final SEPs | ? | ? | ❌ | |
| 2549 | TTL for List Results | ✅ 2025-11-25 | ✅ | ✅ | **READ** - TTL + cacheScope |
| 2567 | Sessionless MCP | ✅ 2026-03-11 | ✅ | ✅ | **READ** - Sessionless MCP |
| 2575 | Make MCP Stateless | ✅ 2025-06-18 | ✅ | ✅ | **READ** - Stateless MCP |
| 2577 | Deprecate Roots, Sampling, Logging | 2026-07-28 | ❌ | | Deprecated in 2026-07-28 |
| 2596 | Feature lifecycle and deprecation policy | 2026-07-28 | ❌ | | Deprecated in 2026-07-28 |
| 2596 | Feature lifecycle and deprecation policy | 2026-07-28 | ❌ | | Duplicate? |
| 2663 | Tasks extension | ✅ 2026-07-28 | ❌ | | Tasks extension |
| 2663 | Tasks extension | 2026-07-28 | ❌ | | Duplicate? |

---

## Protocol Versions Timeline

| Version | Date | Status | Key Changes |
|---------|------|--------|-------------|
| 2026-07-28 | 2026-07-28 | **Latest** | **Removed sessions**, removed `initialize` handshake, added `server/discover`, per-request capabilities, DPoP, Streamable HTTP replaces SSE, removed SSE resumability, added Tasks extension |
| 2025-11-25 | 2025-11-25 | Final | Streamable HTTP, Elicitation, Tasks, OAuth Client ID Metadata, tool annotations |
| 2025-06-18 | 2025-06-18 | Final | Base protocol with Streamable HTTP, initialize handshake, SSE |
| 2025-03-26 | 2025-03-26 | Deprecated | HTTP+SSE deprecated |
| 2024-11-05 | 2024-11-05 | Final | Previous version |

---

## Specification Versions (from docs/specification/)

| Version | Date | Status |
|---------|------|--------|
| 2026-07-28 | 2026-07-28 | **Latest** (released 2 days ago) |
| 2025-11-25 | 2025-11-25 | Final |
| 2025-06-18 | 2025-06-18 | Final (what our plan was based on) |
| 2025-03-26 | 2025-03-26 | Deprecated (HTTP+SSE deprecated) |
| 2024-11-05 | 2024-11-05 | Final |
| draft | WIP | In progress |

---

## Review Status Summary

| Category | Total | Read | Unread |
|----------|-------|------|--------|
| **Core SEPs (read)** | 8 | 8 | 0 |
| **Core SEPs (unread)** | ~15 | 0 | ~15 |
| **Protocol Versions** | 5 | 2 | 3 |
| **Minor/Other SEPs** | ~30 | 0 | ~30 |

---

## What We've READ (Confirmed)

| SEP | Title | Date | Key Points |
|-----|-------|------|------------|
| **SEP-2575** | Make MCP Stateless | 2025-06-18 | Remove `initialize` handshake, per-request version/capabilities, `server/discover` |
| **SEP-2567** | Sessionless MCP | 2026-03-11 | Remove `Mcp-Session-Id`, explicit state handles |
| **SEP-2243** | HTTP Standardization | 2026-02-04 | `Mcp-Method`, `Mcp-Name` headers, `x-mcp-header` |
| **SEP-2567** | Sessionless MCP | 2026-03-11 | Explicit state handles, session-independent lists |
| **SEP-2549** | TTL for List Results | 2025-11-25 | `ttlMs`, `cacheScope` |
| **SEP-2322** | MRTR | 2026-07-28 | Multi Round-Trip Requests pattern |
| **SEP-2549** | TTL for List Results | 2025-11-25 | `ttlMs`, `cacheScope` |
| **SEP-2243** | HTTP Standardization | 2026-02-04 | `Mcp-Method`, `Mcp-Name`, `x-mcp-header` |

---

## NOT YET READ (Priority Order)

### High Priority (Core Protocol Changes in 2026-07-28)

| SEP | Title | Why Important |
|-----|-------|---------------|
| **SEP-2575** | Make MCP Stateless | Removes `initialize`, adds `server/discover`, per-request caps |
| **SEP-2567** | Sessionless MCP | Removes `Mcp-Session-Id`, explicit handles |
| **SEP-2243** | HTTP Standardization | Streamable HTTP headers |
| **SEP-2322** | MRTR | Multi Round-Trip Requests |
| **SEP-2549** | TTL for List Results | Caching |
| **SEP-2567** | Sessionless MCP | Explicit state handles |
| **SEP-2575** | Make MCP Stateless | Stateless-first |

### New in 2026-07-28 (Not in 2025-11-25)

| Feature | SEP | Description |
|---------|-----|-------------|
| **Removed `initialize`** | SEP-2575 | No more handshake |
| **Removed `Mcp-Session-Id`** | SEP-2567 | No session header |
| **`server/discover`** | SEP-2575 | Required RPC |
| **Per-request capabilities** | SEP-2575 | In `_meta` |
| **DPoP token binding** | SEP-? | RFC 9449 |
| **Streamable HTTP replaces SSE** | SEP-2575 | SSE deprecated |
| **Removed SSE resumability** | SEP-2575 | No `Last-Event-ID` |
| **Tasks extension** | SEP-1686/2663 | Tasks as extension |
| **Elicitation** | SEP-1036/1330 | URL mode + enum improvements |
| **Roots** | SEP-2322 | Deprecated in 2026-07-28 |
| **Sampling** | SEP-2577 | Deprecated in 2026-07-28 |
| **Logging** | SEP-2577 | Deprecated in 2026-07-28 |
| **Tasks extension** | SEP-1686/2663 | Moved to extension |
| **OAuth Client ID Metadata** | SEP-991 | Client registration |
| **OAuth Client Credentials** | SEP-1046/1046 | Client credentials flow |
| **OAuth Protected Resource** | SEP-985 | RFC 9728 alignment |
| **Dynamic Client Registration** | SEP-837/991 | Client ID Metadata Docs |

---

## Priority Reading Order

| Priority | SEP | Title | Est. Time |
|----------|-----|-------|-----------|
| 1 | SEP-2575 | Make MCP Stateless | 30 min |
| 2 | SEP-2567 | Sessionless MCP | 30 min |
| 3 | SEP-2243 | HTTP Standardization | 20 min |
| 4 | SEP-2322 | MRTR | 20 min |
| 5 | SEP-2549 | TTL for List Results | 15 min |
| 6 | SEP-2567 | Sessionless MCP | 30 min |
| 7 | SEP-2243 | HTTP Standardization | 20 min |
| 8 | SEP-2322 | MRTR | 20 min |
| 9 | SEP-2549 | TTL for List Results | 15 min |

---

## What We've Already Implemented (Mecris)

| Feature | Status | Notes |
|---------|--------|-------|
| TimezoneService | ✅ | Fixed Bug #1, #2 |
| ReviewPumpCore | ✅ | Python + Kotlin parity |
| Walk Cache pg_notify | ✅ | Instant invalidation |
| Auth: JWKS timeout=60s, no cache | ✅ | Fixed 401 errors |
| Auth: POCKET_ID_CLIENT_ID | ✅ | Audience validation |
| ReviewPumpCore Python | ✅ | 43 tests pass |
| ReviewPumpCore Kotlin | ✅ | 1:1 port |
| Walk cache pg_notify | ✅ | Instant invalidation |
| Auth token refresh | ✅ | `mecris login` works |
| Streamable HTTP | ❌ | Still on SSE |
| Resources | ❌ | Not implemented |
| Prompts | ❌ | Not implemented |
| Subscriptions | ✅ | pg_notify for walks |
| Elicitation | ❌ | Not implemented |
| Roots | ❌ | Not implemented |
| Sampling | ❌ | Not implemented |
| Tasks | ❌ | Not implemented |
| Streamable HTTP | ❌ | Still on SSE |
| DPoP | ❌ | Not implemented |
| OAuth 2.1 | ❌ | Not implemented |
| server/discover | ❌ | Not implemented |
| Per-request caps | ❌ | Not implemented |

---

## Next Steps

1. **Read SEP-2575** (Make MCP Stateless) - 30 min
2. **Read SEP-2567** (Sessionless MCP) - 30 min
3. **Read SEP-2243** (HTTP Standardization) - 20 min
3. **Read SEP-2322** (MRTR) - 20 min
3. **Read SEP-2549** (TTL for List Results) - 15 min
4. **Read SEP-2567** (Sessionless MCP) - 30 min
4. **Read SEP-2243** (HTTP Standardization) - 20 min
4. **Read SEP-2322** (MRTR) - 20 min
4. **Read SEP-2549** (TTL for List Results) - 15 min

Then rewrite the plan document to target **2026-07-28 spec** instead of 2025-06-18.