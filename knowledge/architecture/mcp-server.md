---
type: Architecture
title: MCP Server (`mcp_server.py`)
description: The Python stdio MCP server is the live integration layer for accountability, budget, language, scheduling, and health operations.
generated: { by: agent/gpt-5.6-sol, at: 2026-09-06T23:20:00Z }
sources:
  - resource: mcp_server.py
  - resource: services/credentials_manager.py
  - resource: .mcp.json
  - resource: .pi/extensions/mecris/index.ts
  - resource: docs/MCP_INTEGRATION_SPEC.md
---
concept_id: "architecture/mcp-server"

# MCP Server

`mcp_server.py --stdio` is the canonical live backend. MCP-capable harnesses can launch it through `.mcp.json`. Pi does not consume `.mcp.json` as an MCP client; `.pi/extensions/mecris/index.ts` starts the same Python server and registers its tools as native Pi tools.

## Pi bridge

The bridge registers all Mecris tools but initially activates only `get_narrator_context` and `mecris_load_tools`. Additional capabilities are enabled by keyword through the loader. This limits the schema surface seen by a model while preserving access to the full tool catalog.

Pi exposes two status paths:

- `/status`: native deterministic command; directly calls `get_narrator_context` and formats the result without an LLM turn.
- `/mecris [focus]`: sends a status request to the selected model for richer interpretation.

The bridge hides optional `user_id` fields from core read-only tool schemas. Explicit identity remains supported by the Python functions for intentional multi-user or administrative calls.

## Identity resolution

`services/credentials_manager.py` resolves identity in order: explicit argument, `~/.mecris/credentials.json`, then optional `DEFAULT_USER_ID`. The credentials file is written by `bin/mecris login`. If none is available, tools return `Authentication Required`.

Identity values do not belong in committed prompts or harness configuration. The environment fallback is for standalone recovery, not the normal Pi path.

## Transport caveat

FastMCP structured responses use `structuredContent.result`. Consumers must unwrap `result`; otherwise valid narrator data appears missing. The Pi bridge handles this for deterministic status.

The server is the source of live state. OKF stores durable architecture, decisions, and runbooks—not snapshots of volatile status.

## Related Concepts

- [Deterministic Pi Status and Progressive Context](../decisions/2026-09-06-deterministic-status.md): Records why Pi has separate deterministic and model-mediated status paths.
- [Narrator Context](narrator-context.md): Unified live payload used by both paths.
- [Budget Governor Service](services/budget-governor.md): Budget checks and routing recommendations.
- [Language Coaching Service](services/coaching-service.md): Language review status and controls.
- [PocketID Authentication](services/auth-service.md): Login and credential lifecycle.
