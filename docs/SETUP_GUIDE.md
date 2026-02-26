# 🛠️ Mecris Setup & Configuration Guide

This guide covers the technical setup for the Mecris MCP server and how to configure it for different agents (Gemini and Claude).

## 1. Prerequisites

- Python 3.13+
- `uv` for dependency management (`brew install uv`)
- Environment variables configured in `.env` (Beeminder, Twilio, etc.)

## 2. Server Installation

```bash
# Initialize virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## 3. Running the Server (stdio mode)

The MCP server is primarily used via `stdio` for integration with CLI agents.

```bash
uv run mcp_server.py --stdio
```

For debugging or HTTP access:
```bash
uv run python mcp_server.py
# Server will be available at http://localhost:8000
```

## 4. Agent Configuration

### Gemini CLI
Configuration is located in `.gemini/settings.json`.

```json
{
    "mcpServers": {
        "mecris": {
            "command": "uv",
            "args": [
                "--quiet",
                "run",
                "--no-sync",
                "mcp_server.py",
                "--stdio"
            ],
            "env": {
                "PYTHONPATH": "."
            }
        }
    }
}
```

### Claude Code
Claude Code can be configured using the same `.mcp.json` or by following Claude's internal MCP setup process. 

### Shared MCP Config (`.mcp.json`)
```json
{
  "mcpServers": {
    "mecris": {
      "command": "uv",
      "args": [
        "--quiet",
        "run",
        "--no-sync",
        "mcp_server.py",
        "--stdio"
      ]
    }
  }
}
```

## 5. Maintenance Commands

- **Check Health**: `curl http://localhost:8000/health`
- **Run Tests**: `PYTHONPATH=. uv run python3 tests/test_mecris.py`
- **Stop Server**: `pkill -f mcp_server.py`
