# Mecris Portability & Antigravity (Agy) Integration

This document outlines the steps required to ensure the Mecris project and its MCP configuration are portable to the **Antigravity CLI (Agy)** and other environments.

## 1. Absolute Path Issue

The current `.gemini/settings.json` uses absolute paths for the `mecris` MCP server:

```json
"mecris": {
  "command": "uv",
  "args": [
    "--quiet",
    "run",
    "--no-sync",
    "--offline",
    "/Users/yebyen/w/mecris/mcp_server.py",
    "--stdio"
  ]
}
```

**Recommendation:** Replace absolute paths with environment variables or relative paths if supported by the client. For Agy, consider a configuration that resolves the project root dynamically.

## 2. Python Environment & `uv`

Mecris relies on `uv` for fast, reproducible Python execution.
- Ensure `uv` is installed on the target machine.
- The `PYTHONPATH` must include the project root to resolve local services.

## 3. Database Dependency (Neon)

Mecris has migrated fully to **Neon (Postgres)**. The `NEON_DB_URL` environment variable is MANDATORY.
- The SQLite fallback has been removed to ensure consistency across cloud and local modalities.
- Ensure the target environment has network access to Neon.

## 4. OIDC & Authentication

The Python MCP handles authentication via `Depends(get_current_user)`.
- In `standalone` mode, it falls back to the local `credentials.json` or `DEFAULT_USER_ID`.
- In `multi-tenant` mode, it requires a valid JWT from Pocket ID.
- **Portability Tip:** Ensure `~/.mecris/credentials.json` is synced or recreated on the new machine.

## 5. Android Versioning

**CRITICAL:** Always use `make bump-version` with a strictly increasing `versionCode` (VC).
- Downgrading the `versionCode` (as happened when moving from VC 24 to VC 10) causes Android to treat the install as a downgrade, which often leads to **preference loss and data wipes**.
- Current version is fixed to `0.0.1-beta.10` with `versionCode 25`.

## 6. Antigravity CLI (Agy) Specifics

- Antigravity stores session data in `.antigravitycli/` directories.
- To load Mecris into Agy, ensure the MCP server is registered in the Agy global or project configuration.
- Agy may require an SSE (Server-Sent Events) connection if stdio is restricted; `mcp_server.py` already supports this via `app.mount("/mcp", mcp.sse_app())`.

---
*Created on 2026-06-11 to support the transition to the Agy client.*
