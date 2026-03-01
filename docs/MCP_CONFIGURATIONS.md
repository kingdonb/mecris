# Model Context Protocol (MCP) Configurations

This document outlines the various Model Context Protocol (MCP) server configurations used throughout the Mecris project and its associated skills.

*(This document is a work in progress. It is meant to capture the different locations and contexts where MCP servers are defined, such as for GitHub integration, SQLite databases, and other local/remote tools.)*

## Overview

Mecris utilizes MCP to safely expose tools and context to both Gemini CLI and Claude Code. The configuration for these servers can be found in several places, depending on the tool and the agent.

## Configuration Locations

- `.mcp.json` / `claude_desktop_config.json`: Standard configuration locations for Claude Code / Desktop.
- `.gemini/settings.json`: Where Gemini CLI may invoke or map MCP endpoints.
- `.mcp/mecris.json`: Specific configuration for the Mecris system MCP servers.
- **GitHub MCP Server**: Documented and managed via the `github-mcp-setup` skill.
- **Local SQLite / Data Endpoints**: Run through the Python-based MCP servers (e.g., `mcp_server.py`, `mcp_stdio_server.py`).

*(Details to be expanded in upcoming sessions based on `.gemini/skills/README.md` reference.)*
