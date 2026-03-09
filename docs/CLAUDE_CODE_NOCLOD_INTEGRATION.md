# Claude Code & Noclod Integration Brief

## Overview
This document details the configuration and recent fixes required to enable `claude-code` CLI to work with an OpenAI-compatible backend (like Groq) via the `noclod` proxy stack.

## Repository Information
The core proxy and deployment logic resides in:
👉 **[kingdon-ci/noclod](https://github.com/kingdon-ci/noclod)**

## Recent Critical Fixes (March 2026)

### 1. Claude 3.7 Compatibility (Thinking Mode)
The recent `claude-code` CLI updates (v2.1.x+) introduced a `thinking` parameter in the request payload. The proxy's Pydantic models were updated to support this:
- **File**: `src/models/claude.py`
- **Change**: Added `ClaudeThinkingConfig` and set `extra = "allow"` on all request models to prevent 500 errors when new, unknown fields are sent by the CLI.

### 2. MacOS Tahoe Container Runtime Stability
On MacOS Tahoe (26.x), the experimental `mocker` shim occasionally fails to bind ports to `localhost`. 
- **Fix**: Switched from `mocker` to the native `container` CLI in the `litellm-deploy/Makefile`.
- **Dynamic IP**: Updated `start-dev.sh` to dynamically discover the container's IP using `container ls` and inject it into the proxy's `OPENAI_BASE_URL`.

### 3. API Constraints & Port Management
- **Token Clamping**: Hard-clamped `max_tokens` to `16384` in `src/core/config.py` to match Groq's API limits and avoid 400 errors.
- **Port Isolation**: Enforced `PORT=8082` for the proxy to prevent collisions with the main Mecris MCP server (port 8000).
- **Authentication**: Ensured `OPENAI_API_KEY` in the proxy matches the LiteLLM `LITELLM_MASTER_KEY` to avoid "401 Unauthorized" errors disguised as "500 Connection errors".

## Operational Commands
To restart the stack within the `noclod` repository:
```bash
make stop
make dev
source vars
claude
```
