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

### Claude Desktop (macOS)

For Claude Desktop, configuration is typically located at `~/Library/Application Support/Claude/claude_desktop_config.json`. 

> **Note:** Claude Desktop requires absolute paths for the `command`, `args`, and `env` fields.

```json
{
  "mcpServers": {
    "mecris": {
      "command": "/opt/homebrew/bin/uv",
      "args": [
          "--quiet",
          "run",
          "--project", "/Users/yebyen/w/mecris",
          "/Users/yebyen/w/mecris/mcp_server.py",
          "--stdio"
      ],
      "cwd": "/Users/yebyen/w/mecris",
      "env": {
          "PYTHONPATH": "/Users/yebyen/w/mecris"
      }
    }
  }
}
```

### Claude Code
Claude Code can be configured using the `.mcp.json` file in the project root or by following Claude's internal MCP setup process. 

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
      ],
      "env": {
        "PYTHONPATH": ".",
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

## 5. Spin Backend Configuration (Cloud)

The Mecris-Go sync service requires specific variables to be set in Fermyon Cloud for OIDC verification and PII encryption.

### Required Secrets

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `oidc_discovery_url` | The URL to your OIDC provider's configuration. | `https://metnoom.urmanac.com/.well-known/openid-configuration` |
| `master_encryption_key` | 32-byte key in hex format (64 chars) for AES-256-GCM. | `000102...1d1e` |
| `db_url` | Neon PostgreSQL connection string. | `postgres://user:pass@host/db` |

### Setting Variables via Spin CLI

```bash
spin cloud variable set oidc_discovery_url="https://<your-oidc-domain>/.well-known/openid-configuration"
spin cloud variable set master_encryption_key="$(openssl rand -hex 32)"
spin cloud variable set db_url="<your-neon-db-url>"
```

## 6. Maintenance Commands

- **Check Health**: `curl http://localhost:8000/health`
- **Run Tests**: `PYTHONPATH=. uv run python3 tests/test_mecris.py`
