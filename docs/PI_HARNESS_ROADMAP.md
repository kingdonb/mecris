# 🥧 Pi Harness Integration Roadmap

> Bringing Mecris into the [Pi coding agent](https://github.com/earendil-works) — the
> open-source harness — at parity with Claude Code, Gemini CLI, Antigravity CLI, and
> the native `py_harness/`.

**Status**: ✅ Working bridge (v0.0.1) — Mecris MCP tools are callable from Pi.
**Author**: Claude Opus 4.x, driving the Pi harness, at Kingdon's direction (2026-07).

---

## Why Pi

- **Open source.** Antigravity works but is closed; Gemini CLI got folded into it.
  Pi is open, hackable, and local-first — the same philosophy as Mecris itself
  ("cloud-coordinated, local-first", see `ARCHITECTURE.md`).
- **Bring-your-own-backend.** Pi speaks to GitHub Copilot, Groq, OpenAI, Anthropic,
  Google, and custom providers. You get a Mecris status update "in the normal way"
  regardless of which model is behind the wheel.
- **Extensions, not plugins-you-can't-see.** The whole integration is ~350 lines of
  auditable TypeScript in `.pi/extensions/mecris/`.

## What was built

`.pi/extensions/mecris/index.ts` — a bridge extension that:

1. **Spawns the Mecris MCP server** over stdio using the official
   `@modelcontextprotocol/sdk` client, launching `mcp_stdio_server.py` with the repo
   `.venv` Python.
2. **Registers all 34 Mecris tools** as native Pi tools (prefixed `mecris_`), converting
   each tool's MCP JSON-Schema input into a TypeBox schema so Pi validates arguments the
   same way it validates its built-in `read`/`bash`/`edit` tools.
3. **Lazy-loads** for token efficiency: only a small read-only "core" status set is active
   at startup; the other ~29 write/admin tools are deferred behind a `mecris_load_tools`
   loader (Pi's native deferred-tool-loading pattern).
4. Adds **`/mecris`** (status update in the normal way) and **`/mecris-reconnect`** commands.
5. Cleans up the subprocess on `session_shutdown`.

### Verified end-to-end
- `pi --list-models` loads the extension factory cleanly (connects + registers).
- `claude-haiku-4.5` via GitHub Copilot called `mecris_get_narrator_context` and
  summarized real goal/budget/runway data.
- The deferred path works: a model called `mecris_load_tools` then
  `mecris_get_recent_usage` and returned real usage rows.

## Harness parity matrix

| Capability | Claude Code | Gemini CLI | Antigravity CLI | `py_harness` (native) | **Pi bridge** |
|---|---|---|---|---|---|
| Config format | `.mcp.json` | `.gemini/settings.json` | `~/.gemini/antigravity-cli/mcp_config.json` | Python `StdioServerParameters` | `.pi/extensions/mecris/` (TS) |
| Server entrypoint | `mcp_server.py --stdio` | `mcp_server.py --stdio` | `mcp_server.py --stdio` | `mcp_stdio_server.py` | `mcp_stdio_server.py` |
| Binds port 8080 bridge | ⚠️ yes | ⚠️ yes | ⚠️ yes | ✅ no | ✅ no |
| Tool transport | MCP stdio | MCP stdio | MCP stdio | MCP stdio | MCP stdio |
| Lazy tool loading | ❌ all tools | ❌ all tools | ❌ all tools | ✅ `filter_core_tools` (1 tool) | ✅ core set + loader |
| Backend model | Claude | Gemini | Gemini | Ollama (local) | any Pi provider |
| Native tool-calling | ✅ | ✅ | ✅ | optional (prompt fallback) | ✅ |
| Open source harness | ❌ | ❌ | ❌ | ✅ (ours) | ✅ |

**Note on the port-8080 choice:** the other CLIs launch `mcp_server.py --stdio`, which
*also* starts the FastAPI Android bridge on `0.0.0.0:8080`. Running two of them at once
hard-fails on the bound port (see the "port conflict" fix in `session_log.md`). The Pi
bridge deliberately follows `py_harness` and launches `mcp_stdio_server.py` (scheduler +
stdio, **no** HTTP bridge), so it coexists with any other running harness.

## Differences vs the native `py_harness/`

The native harness is a purpose-built local-inference ReAct loop. The Pi bridge is a
general-purpose agent that *hosts* Mecris as tools. Key differences:

| Aspect | `py_harness/` | Pi bridge |
|---|---|---|
| Loop | Hand-rolled `run_loop` in `mecris_harness.py` | Pi's agent loop |
| Model | Ollama / Hailo edge (`gemma4`, `qwen2:1.5b`) | Any Pi provider (Copilot, Groq, …) |
| Core tool set | exactly `get_narrator_context` | 5 read-only status tools + loader |
| Prompt-based tool fallback | ✅ (for models without native tools) | not needed (Pi handles serialization) |
| `get_narrator_context` output pruning | ✅ hard-coded for NPU cache limits | ❌ not yet (big-context models don't need it) |
| Caveman/RTK compression persona | ✅ system prompt | ❌ not ported (see roadmap) |
| History pruning | `prune_history` (system + last 20) | Pi's own compaction |
| Presence / `ACTIVE_HUMAN` recording | via MCP server | via MCP server (same) |

## Roadmap

### Now — v0.0.1 (done)
- [x] MCP stdio bridge extension, 34 tools, TypeBox schema conversion.
- [x] Lazy loading via `mecris_load_tools`.
- [x] `/mecris` and `/mecris-reconnect` commands.
- [x] Clean subprocess lifecycle on shutdown.

### Next — v0.1.0 (parity polish)
- [ ] **Caveman persona parity**: ship an `--append-system-prompt` snippet (or a Pi
      prompt-template) that mirrors the `py_harness` "Brain big, mouth small" narrator so
      the *voice* matches across harnesses.
- [ ] **Narrator-context pruning option**: port the defensive `get_narrator_context`
      payload pruning behind an env flag for when Pi drives a small local model.
- [ ] **Result rendering**: `renderResult` so Mecris tool output shows as a compact card
      in the Pi TUI instead of raw JSON.
- [ ] **Package it**: publish as a pi package (`pi install git:github.com/kingdonb/mecris`)
      so it installs without the local `.pi/extensions` copy. See `docs/packages.md`.
- [ ] **Skill bridge**: expose the four Gall-loop skills (`/mecris-orient`, `/mecris-plan`,
      `/mecris-archive`, `/mecris-pr-test`) as Pi skills or commands.

### Later — v0.2.0 (harness-native features)
- [ ] **Auto-status on session start**: optional `session_start` turn that greets you with
      your runway/budget (opt-in; respects quiet hours from the nag engine).
- [ ] **Groq odometer hook**: record Pi's own Groq token usage back into Mecris via
      `record_groq_reading` using Pi's `after_provider_response` event.
- [ ] **Budget governor gate**: a `tool_call`/`before_provider_request` guard that warns
      or blocks when `get_budget_governor_status` says the budget is spent.
- [ ] **Local-first mode**: wire Pi's custom-provider API to the Hailo-ollama edge node so
      Pi can run the same local model as `py_harness` when offline.

### Open questions
- Should Mecris ship *one* canonical harness config generator (`mecris init <harness>`)
  that writes the right config for Claude Code / Gemini / Antigravity / Pi from a single
  source of truth? Would kill the config drift between the five configs today.
- Revive the cloud Spin/WASM backend (offline since ~April 2026) so the Pi bridge can fail
  over to the cloud hub like the Android app does.

---

*Built by Claude Opus driving Pi, for Kingdon. The forest remembers every missed step.* 🐗
