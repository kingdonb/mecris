# Using Pi and Mecris Together

> How to drive the Mecris personal accountability system from the
> [Pi coding agent](https://github.com/earendil-works) — the open-source,
> bring-your-own-model harness.

This guide covers setup, daily use, configuration, troubleshooting, and how the
Pi bridge relates to the other Mecris harnesses (Claude Code, Gemini CLI,
Antigravity CLI, and the native `py_harness/`).

See also:
- [`docs/PI_HARNESS_ROADMAP.md`](PI_HARNESS_ROADMAP.md) — parity matrix and roadmap
- [`.pi/extensions/mecris/README.md`](../.pi/extensions/mecris/README.md) — extension reference
- `session_log.md` (2026-07-15 entry) — how and why this was built

---

## 1. What this integration is

Pi intentionally ships **without built-in MCP support** — you add it as an
extension. This repo ships that extension at `.pi/extensions/mecris/`: a
~350-line TypeScript bridge that:

- **Spawns the Mecris MCP server** (`mcp_stdio_server.py`) as a subprocess over
  stdio, using the official `@modelcontextprotocol/sdk` client.
- **Registers all 34 Mecris tools** as native Pi tools, prefixed `mecris_`
  (e.g. `mecris_get_narrator_context`). Each tool's MCP JSON-Schema input is
  converted to a TypeBox schema, so Pi validates arguments exactly like its
  built-in `read`/`bash`/`edit` tools.
- **Lazy-loads tools**: only 5 read-only status tools are active at startup;
  the other ~29 write/admin tools sit behind a `mecris_load_tools` loader that
  the model calls on demand. This keeps context overhead low, in the spirit of
  `py_harness`'s `filter_core_tools`.
- Adds two commands: **`/mecris`** and **`/mecris-reconnect`**.
- Shuts the subprocess down cleanly when your Pi session ends.

Because Pi is provider-agnostic, this means Mecris now works with **any model
Pi can reach**: GitHub Copilot (Claude, GPT, Gemini models), Groq, Anthropic,
OpenAI, Google, or a custom/local provider.

## 2. Prerequisites

| Requirement | Check with | Notes |
|---|---|---|
| Pi installed | `pi --help` | `npm i -g @earendil-works/pi-coding-agent` or Homebrew |
| A Pi provider configured | `pi --list-models` | e.g. GitHub Copilot or Groq auth in `~/.pi/agent/auth.json` |
| Node.js ≥ 20 | `node --version` | needed for the extension's npm deps |
| Mecris Python venv | `ls .venv/bin/python` | `uv venv && uv pip install -r requirements.txt` |
| Mecris `.env` configured | `cat .env` | Beeminder, Twilio, Neon credentials, etc. |

The bridge talks to the same Neon database and Beeminder/Twilio integrations as
every other harness. If `python mcp_stdio_server.py` works, the bridge will too.

## 3. Setup

### 3.1 One-time install

From the repo root:

```bash
cd .pi/extensions/mecris
npm install          # fetches @modelcontextprotocol/sdk into node_modules/
cd ../../..
```

`node_modules/` is gitignored; `package.json` and `package-lock.json` are
committed, so this step is reproducible on any clone.

### 3.2 Trust the project

Pi auto-discovers project-local extensions from `.pi/extensions/*/index.ts`,
but only after you trust the project (extensions run arbitrary code):

```bash
cd /path/to/mecris
pi
# Accept the project-trust prompt on first run
```

After trusting, the bridge loads automatically every time you run `pi` inside
the Mecris repo. On startup you should see a notification like:

```
Mecris bridge online: 34 tools (5 active, rest via mecris_load_tools).
```

### 3.3 Quick test without trusting (explicit load)

```bash
pi -e ./.pi/extensions/mecris/index.ts \
   --provider github-copilot --model claude-haiku-4.5 \
   --no-session \
   -p "Call mecris_get_narrator_context and give me a one-line status."
```

If that prints a summary of your goals/budget/runway, everything works.

## 4. Daily use

### 4.1 Ask in the normal way

Just talk to it. The narrator-context tool is active by default, so any of
these work in a normal Pi session:

- *"What's my Mecris status?"*
- *"Am I on track today? What's urgent?"*
- *"How much budget is left and what's the burn rate?"*
- *"Which Beeminder goals are closest to derailing?"*

The model will call `mecris_get_narrator_context` (and the other core status
tools) and summarize.

### 4.2 The `/mecris` command

For a one-shot status update:

```
/mecris                  # general status: urgent goals, runway, budget
/mecris greek reviews    # status focused on a topic
```

This injects a user message that instructs the model to call the narrator
context first — the same "status update in the normal way" you get from the
other harnesses.

### 4.3 Actions beyond status (deferred tools)

Only 5 read-only tools are active at startup:

| Active at startup | Purpose |
|---|---|
| `mecris_get_narrator_context` | The main unified status (goals, runway, budget, urgency) |
| `mecris_get_beeminder_status` | Goal portfolio with risk classification |
| `mecris_get_budget_status` | Budget and burn-rate |
| `mecris_get_daily_aggregate_status` | Daily progress (the Majesty Cake 🍰) |
| `mecris_get_system_health` | Service/dependency health |

Everything else — recording usage, sending alerts, adjusting goals, language
levers, notifications, scheduler queue, weather, bookmarks, data export — is
**registered but inactive** until needed. When you ask for one of those, the
model calls the loader:

```
mecris_load_tools(query: "usage")      # activates matching tools
mecris_load_tools(query: "beeminder")
mecris_load_tools(query: "all")        # activates everything
```

You don't have to do anything; the loader tool's description and prompt
guidelines steer the model to use it. Example requests that exercise this path:

- *"Record this session's token usage in Mecris."*
- *"Enqueue a reminder for me in 30 minutes."*
- *"What did I bookmark about Talos recently?"*
- *"Set the Greek review pump multiplier to 1.5."*

### 4.4 Reconnecting

If the Python server dies or you restart the Mecris backend:

```
/mecris-reconnect
```

This tears down the old subprocess and spawns a fresh one, registering any new
tools, without a full `/reload` of Pi.

### 4.5 Choosing models

Any Pi provider works. Useful combinations:

```bash
# Big-context, high quality (default from ~/.pi/agent/settings.json)
pi

# Explicit fast/cheap model for quick status checks
pi --provider github-copilot --model claude-haiku-4.5

# Non-interactive one-shot (scripting / cron-friendly)
pi --no-session -p "/mecris"
```

**Known issue:** `groq/openai/gpt-oss-20b` fails to serialize tool-call
arguments as JSON ("Failed to parse tool call arguments"). This is a
model-side quirk, not the bridge — other Groq models and all Copilot models
tested work fine.

## 5. Configuration

The bridge is configured entirely by environment variables (set them in your
shell before launching `pi`):

| Variable | Default | Purpose |
|---|---|---|
| `MECRIS_HOME` | repo root (3 levels above the extension) | Location of the Mecris checkout |
| `MECRIS_PYTHON` | `$MECRIS_HOME/.venv/bin/python` | Python interpreter for the MCP server |
| `MECRIS_STDIO_SCRIPT` | `$MECRIS_HOME/mcp_stdio_server.py` | Server entrypoint |
| `MECRIS_CORE_TOOLS` | the 5 status tools above | Comma-separated list of tools active at startup (upstream names, no `mecris_` prefix) |

Example — minimal py_harness-style single-tool startup:

```bash
MECRIS_CORE_TOOLS=get_narrator_context pi
```

The Mecris server itself reads the repo `.env` (Beeminder, Twilio, Neon,
encryption keys) exactly as it does for every other harness. The bridge passes
`PYTHONPATH=$MECRIS_HOME` and inherits your shell environment.

## 6. How it coexists with other harnesses

**Important design decision:** the Claude Code / Gemini / Antigravity configs
all launch `mcp_server.py --stdio`, which *also* binds the FastAPI Android
bridge on `0.0.0.0:8080`. Two of those at once fail on the bound port.

The Pi bridge instead launches **`mcp_stdio_server.py`** (scheduler + stdio,
no HTTP bridge), matching the native `py_harness`. Consequences:

- ✅ You can run Pi alongside Claude Code, Antigravity, or the Android-serving
  instance without port conflicts.
- ✅ The scheduler still starts, and participates in the distributed leader
  election (`scheduler_election` table) like any other instance — only one
  leader nags at a time.
- ⚠️ A Pi-spawned server does **not** serve the Android app. If you want
  the phone to sync through your machine, keep a `mcp_server.py` instance (or
  another harness) running for port 8080.

Each Pi session spawns its **own** server subprocess, and it exits with the
session. State lives in Neon, so concurrent instances see the same reality.

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "Mecris bridge offline: ... stdio script not found" | Wrong repo location / `MECRIS_HOME` | Run `pi` from the repo root, or set `MECRIS_HOME` |
| Bridge offline, connect error | venv broken or deps missing | `.venv/bin/python mcp_stdio_server.py` by hand and read the error; check `/tmp/mecris_stdio.log` |
| Slow startup (~3s pause) | MCP server cold start (Python imports, scheduler) | Normal; it connected in ~2.7s in testing |
| Tools missing from the model's view | They're deferred | Ask the model to use `mecris_load_tools`, or say what you want — it will |
| "Failed to parse tool call arguments as JSON" | Model-side serialization bug (seen on groq gpt-oss-20b) | Switch models/providers |
| Stale data / server restarted | Old subprocess connection | `/mecris-reconnect` |
| Extension not loading at all | Project not trusted, or `npm install` skipped | Trust the project; run `npm install` in `.pi/extensions/mecris/` |
| Port 8080 already in use errors | You launched `mcp_server.py --stdio` elsewhere | Fine — the Pi bridge doesn't touch 8080; the conflict is between the *other* harnesses |

Server-side logs: the stdio server writes to `/tmp/mecris_stdio.log`
(override with `MCP_STDIO_LOG_FILE`).

## 8. Comparison with the other harnesses

| | Claude Code | Gemini CLI | Antigravity CLI | `py_harness` | **Pi** |
|---|---|---|---|---|---|
| Config | `.mcp.json` | `.gemini/settings.json` | `~/.gemini/antigravity-cli/mcp_config.json` | Python code | `.pi/extensions/mecris/` |
| Entrypoint | `mcp_server.py --stdio` | same | same | `mcp_stdio_server.py` | `mcp_stdio_server.py` |
| Binds :8080 | yes ⚠️ | yes ⚠️ | yes ⚠️ | no | no |
| Lazy tool loading | no | no | no | yes (1 tool) | yes (5 + loader) |
| Models | Claude only | Gemini only | Gemini only | local Ollama | **any provider** |
| Open source harness | no | no | no | yes | **yes** |

Not yet ported from `py_harness` (see the roadmap): the Caveman
"brain big, mouth small" persona, and defensive `get_narrator_context` payload
pruning for small local models.

## 9. Under the hood (for hackers)

Flow of a single status request:

```
you ──> Pi agent loop ──> model (any provider)
                             │  tool call: mecris_get_narrator_context
                             ▼
             .pi/extensions/mecris/index.ts (bridge)
                             │  MCP JSON-RPC over stdio
                             ▼
             .venv/bin/python mcp_stdio_server.py
                             │
              ┌──────────────┼───────────────┐
              ▼              ▼               ▼
          Neon DB       Beeminder API     Twilio / etc.
```

Key implementation points in `index.ts`:

- **Async extension factory**: connects + registers tools *before* Pi startup
  completes, so tools are visible immediately.
- **Load-safe vs runtime APIs**: `pi.registerTool()` is legal during load, but
  `pi.getActiveTools()`/`setActiveTools()` are runtime action methods — the
  lazy-loading active-set change is deferred to `session_start`.
- **Schema conversion**: a ~60-line recursive JSON-Schema→TypeBox converter
  handles strings/ints/numbers/booleans/arrays/objects, optionality via
  `required`, and pydantic's `default: null` quirk for `Optional[...]` params.
- **Result mapping**: MCP `content` items (text/resource) are flattened into
  Pi text results; MCP `isError` maps to Pi's `isError`.

To extend it: edit `.pi/extensions/mecris/index.ts` and run `/reload` in Pi.

---

*Written by Claude Opus driving the Pi harness, 2026-07. The forest remembers
every missed step.* 🐗
