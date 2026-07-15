# Mecris ↔ Pi bridge extension

Brings the Mecris MCP server into the [Pi coding agent](https://github.com/earendil-works)
as native Pi tools. See [`docs/PI_HARNESS_ROADMAP.md`](../../../docs/PI_HARNESS_ROADMAP.md)
for the full parity analysis and roadmap.

## Install

This directory is auto-discovered by Pi as a project-local extension
(`.pi/extensions/*/index.ts`) once you trust the project. From the repo root:

```bash
cd .pi/extensions/mecris && npm install    # one-time: fetch @modelcontextprotocol/sdk
```

Then just run `pi` in the repo. Or load it explicitly for a quick test:

```bash
pi -e ./.pi/extensions/mecris/index.ts
```

## Use

- Ask for a status update in the normal way, e.g. *"what's my Mecris status?"* — the model
  calls `mecris_get_narrator_context`.
- `/mecris [focus]` — one-shot status update command.
- `/mecris-reconnect` — restart the MCP bridge without a full `/reload`.
- Non-core tools are deferred; the model activates them via `mecris_load_tools`.

## Config (env vars)

| Var | Default | Purpose |
|---|---|---|
| `MECRIS_HOME` | repo root (3 levels up) | Mecris checkout location |
| `MECRIS_PYTHON` | `<home>/.venv/bin/python` | Python interpreter |
| `MECRIS_STDIO_SCRIPT` | `<home>/mcp_stdio_server.py` | stdio entrypoint (no port-8080 bridge) |
| `MECRIS_CORE_TOOLS` | 5 read-only status tools | comma-separated active-at-startup set |

## Why `mcp_stdio_server.py` and not `mcp_server.py --stdio`

The other harness configs launch `mcp_server.py --stdio`, which also binds the FastAPI
Android bridge on `0.0.0.0:8080`. Two of those at once hard-fail on the port. This bridge
follows the native `py_harness` and uses `mcp_stdio_server.py` (scheduler + stdio only), so
it coexists with any other running harness.
