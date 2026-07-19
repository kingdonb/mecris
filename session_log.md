# Session Log: Unified MCP stdio + HTTP Bridge for Mecris

**Date:** 2026-07-19
**Branch:** `feat/unified-mcp-http-bridge`
**Primary Model:** nemotron-3-ultra-550b-a55b:free (via OpenRouter)
**Human:** yebyen

---

## Summary

Consolidated the Mecris MCP server into a **single process** that serves both:
- **stdio MCP** → Pi coding agent (and other stdio clients)
- **HTTP bridge on :8080** → Android app (walk uploads, heartbeats)

Eliminated the need for manual `tmux` sessions, duplicate schedulers, and port conflicts.

---

## Problem

The Mecris architecture had two separate entry points:
1. `mcp_stdio_server.py` — for Pi/stdin clients (no HTTP)
2. `mcp_server.py` — for HTTP/Android (no stdio MCP)

This caused:
- **Port 8080 conflicts** when both ran
- **Two schedulers** (race conditions on Neon leader election)
- **Manual tmux** required to keep HTTP bridge alive
- **Silent failures** — Pi extension ignored stderr, hid startup crashes

---

## Solution

### 1. `mcp_server.py` — Single Canonical Entry Point

```python
# Always starts HTTP thread (daemon) on :8080
http_thread = threading.Thread(target=run_http_server, daemon=True)
http_thread.start()

if "--stdio" in sys.argv:
    # Trust the flag — Pi's StdioClientTransport provides a pipe
    asyncio.run(run_stdio_with_scheduler())
else:
    # Interactive/background: keep process alive for HTTP
    signal.pause()
```

**Key behaviors:**
- HTTP thread starts **immediately** (before stdio logic)
- `--stdio` flag **overrides** stdin detection — always runs MCP server
- After stdio client disconnects: process **stays alive** (HTTP bridge persists)
- Rich stderr logging: `[MECRIS MAIN] ...` for debugging

### 2. `.pi/extensions/mecris/index.ts` — Robust Connection

```typescript
// Capture Python stderr to surface import/startup errors
transport = new StdioClientTransport({
  command: resolvePython(),
  args: [STDIO_SCRIPT, "--stdio"],
  cwd: MECRIS_HOME,
  env: { ...process.env, PYTHONPATH: MECRIS_HOME },
  stderr: "pipe",  // was "ignore"
});

if (transport.stderr) {
  transport.stderr.on("data", (chunk) => {
    stderrOutput += chunk.toString();
  });
}
```

**Improvements:**
- `stderr: "pipe"` + event handler → errors visible in Pi notifications
- Spawns `mcp_server.py --stdio` (not old `mcp_stdio_server.py`)
- `/mecris-reconnect` command for live recovery
- Lazy-loading: core tools active, rest via `mecris_load_tools`

---

## Files Changed

| File | Purpose |
|------|---------|
| `mcp_server.py` | Unified stdio + HTTP server; `--stdio` flag; survives client disconnect |
| `.pi/extensions/mecris/index.ts` | Captures stderr; spawns unified server; lazy tool loading |

---

## Commits

```
bfdbc38 fix: Ensure MCP stdio + HTTP bridge runs as single process
ed6f856 fix: Read Python stderr asynchronously to avoid blocking Pi startup
1507744 fix: Scope stderrOutput outside try/catch block
```

---

## Verification

```bash
# 1. Start Pi with extension
pi -e ./.pi/extensions/mecris/index.ts --continue

# 2. Health check (HTTP bridge)
curl -s http://127.0.0.1:8080/health
# {"status":"healthy","home_server_active":true,"neon_connected":true,...}

# 3. MCP tool call (via Pi)
# > Call mecris_get_narrator_context
# ✓ Returns full context with Android pulse, budget, goals

# 4. Android app: Settings → Backend → "Local (Python: 8080)"
#    Walk sync → Cloud Sync: Success
```

---

## Attribution

**Architecture & implementation:** nemotron-3-ultra-550b-a55b:free (via OpenRouter)  
**Human direction, testing, integration:** yebyen  
**Pi harness integration:** Pi coding agent (earendil-works/pi-coding-agent)  
**Mecris framework:** kingdonb/mecris (Gall-loop skills, MCP tools)

---

## Next Steps

- [ ] Android app: verify failover to cloud (Akamai/Fermyon) when local down
- [ ] Add structured logging to HTTP thread (file + stdout)
- [ ] Consider systemd/service management for headless deployments
- [ ] Document COZYBEBY operational model in `docs/COZYBEBY.md`