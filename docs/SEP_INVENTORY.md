# MCP Specifications Inventory

**Last Updated**: 2026-07-30  
**Latest Protocol Version**: **2026-07-28 (released this week)**  
**Previous Protocol Version**: **2025-11-25**  
→ **Only ONE spec version between them** (the user was right)

---

## Protocol Versions (Only 2 That Matter)

| Version | Date | Status | Key Change |
|---------|------|--------|------------|
| **2026-07-28** | This week | **Latest** | **Stateless rewrite** - removed sessions, `initialize`, SSE |
| **2025-11-25** | Nov 2025 | Previous | Streamable HTTP, elicitation, tasks, OAuth client ID |
| 2025-06-18 | Jun 2025 | Superseded | Base Streamable HTTP |
| 2025-03-26 | Mar 2025 | Deprecated | HTTP+SSE (deprecated in 2025-06-18) |
| 2024-11-05 | Nov 2024 | Legacy | Pre-Streamable |

---

## SEPs Merged Into Each Version

### 2026-07-28 (Stateless Rewrite) — NEW THIS WEEK
| SEP | Title | Key Change |
|-----|-------|------------|
| 2575 | Make MCP Stateless | Remove `initialize`, add `server/discover`, per-request caps |
| 2567 | Sessionless MCP | Remove `Mcp-Session-Id`, explicit state handles |
| 2577 | Deprecate Roots/Sampling/Logging | **Removed from core** |
| 2596 | Feature lifecycle policy | Deprecation framework |
| 2468 | Require issuer claim | Auth alignment |
| 2663 | Tasks extension | Tasks moved to extension |

### 2025-11-25 (Streamable HTTP + Features)
| SEP | Title | Key Change |
|-----|-------|------------|
| 2243 | HTTP Standardization | Streamable HTTP headers (`Mcp-Method`, `Mcp-Name`) |
| 1036 | URL mode elicitation | Secure out-of-band interaction |
| 1330 | Elicitation enum improvements | Better schema |
| 1686 | Experimental tasks | Tasks primitive |
| 1699 | SSE polling | Resumability |
| 2549 | TTL for List Results | `ttlMs`, `cacheScope` caching |
| 1034 | Elicitation defaults | Default values |
| 1303 | Input validation errors | Tool execution errors |
| 1319 | Decouple request payload | Flexible RPC |
| 2106 | Loosen schema constraints | Less restrictive |
| 991 | OAuth Client ID Metadata | Client registration |
| 1046 | OAuth client credentials | Client creds flow |
| 985 | Protected Resource Metadata | RFC 9207 alignment |
| 835 | Incremental scope consent | `WWW-Authenticate` |
| 973 | Resource icons | Icons for tools/resources |
| 986 | Tool name format | Naming convention |
| 1613 | JSON Schema 2020-12 | Default dialect |

---

## What We've READ (5 SEPs)

| SEP | Title | Merged Into | Key Points |
|-----|-------|-------------|------------|
| **2575** | Make MCP Stateless | 2026-07-28 | Remove `initialize`, add `server/discover`, per-request caps |
| **2567** | Sessionless MCP | 2026-07-28 | Remove `Mcp-Session-Id`, explicit state handles |
| **2243** | HTTP Standardization | 2025-11-25 | `Mcp-Method`, `Mcp-Name` headers, `x-mcp-header` |
| **2549** | TTL for List Results | 2025-11-25 | `ttlMs`, `cacheScope` |
| **2322** | MRTR | 2026-07-28 | Multi Round-Trip Requests pattern |

---

## Critical Gaps for 2026-07-28 Compliance

### Removed in 2026-07-28 (We DON'T need these anymore)
| Feature | SEP | Status |
|---------|-----|--------|
| Roots | 2577 | ✅ Don't implement |
| Sampling | 2577 | ✅ Don't implement |
| Logging | 2577 | ✅ Don't implement |
| `initialize` handshake | 2575 | ✅ Remove if present |
| `Mcp-Session-Id` header | 2567 | ✅ Remove if present |
| SSE transport | 2575 | ❌ Must replace with Streamable HTTP |

### Required in 2026-07-28 (We DON'T have)
| Feature | SEP | Effort |
|---------|-----|--------|
| **Streamable HTTP** (not SSE) | 2243 | High |
| **`server/discover` RPC** | 2575 | Medium |
| **Per-request capabilities** (`_meta`) | 2575 | Medium |
| **`MCP-Protocol-Version` header** | 2575 | Low |
| **DPoP token binding** (RFC 9449) | 2468 | High |
| **OAuth 2.1 + issuer claim** | 2468 | High |
| **Explicit state handles** | 2567 | Medium |
| **Tasks as extension** | 2663 | Medium |

### Required in 2025-11-25 (We DON'T have yet, but needed for 2026-07-28)
| Feature | SEP | Effort |
|---------|-----|--------|
| Resources | 2243 | High |
| Prompts | 2243 | High |
| Elicitation (URL mode) | 1036/1330 | Medium |
| OAuth Client ID Metadata | 991 | Medium |
| Resource icons | 973 | Low |

---

## Mecris Implementation Status

| Feature | Implemented? | 2025-11-25 | 2026-07-28 |
|---------|--------------|------------|------------|
| TimezoneService | ✅ | ✅ | ✅ |
| ReviewPumpCore | ✅ | ✅ | ✅ |
| Walk Cache pg_notify | ✅ | ✅ | ✅ |
| Auth: JWKS timeout=60s | ✅ | ✅ | ✅ |
| Auth: POCKET_ID_CLIENT_ID | ✅ | ✅ | ✅ |
| Streamable HTTP | ❌ | **Required** | **Required** |
| Resources | ❌ | Required | Required |
| Prompts | ❌ | Required | Required |
| Elicitation | ❌ | Required | Required |
| Roots | ❌ | Required | **REMOVED** |
| Sampling | ❌ | Required | **REMOVED** |
| Logging | ❌ | Required | **REMOVED** |
| Tasks | ❌ | Experimental | **Extension** |
| DPoP | ❌ | No | **Required** |
| OAuth 2.1 | ❌ | Partial | **Required** |
| server/discover | ❌ | No | **Required** |
| Per-request caps | ❌ | No | **Required** |
| MCP-Protocol-Version | ❌ | No | **Required** |
| Mcp-Method/Mcp-Name | ❌ | Required | **Required** |

---

## Next Steps

1. **Read 4 critical 2026-07-28 SEPs** (2577, 2596, 2468, 2663) — ~1 hour
2. **Read 3 key 2025-11-25 gap SEPs** (1036, 991, 973) — ~1 hour
3. **Rewrite `MCP_STANDARDS_UPDATE_PLAN.md`** targeting 2026-07-28
4. **Update `CLOUD_DEPLOYMENT_PLAN.md`** for Android service mesh