# Session Log: 2026-07-15 (Pi Coding Agent Integration — Open-Source Parity)

## Context
- **Date**: Tuesday, July 15, 2026 (Local)
- **Status**: Built a TypeScript extension bridging Mecris MCP into the Pi coding agent at parity with Claude Code, Gemini CLI, Antigravity CLI, and the native `py_harness/`.
- **Narrator**: Claude Opus (driving the Pi harness)
- **Goal**: Reach parity with all five harnesses. You get a Mecris status update "in the normal way" regardless of which agent or model is driving.

## Accomplishments

### 1. Built the Pi Extension Bridge (`.pi/extensions/mecris/`)
- **~350 lines of TypeScript** in `index.ts` (+ `package.json`, `README.md`, `.gitignore`).
- **Spawns `mcp_stdio_server.py`** over stdio using the official `@modelcontextprotocol/sdk` client (npm install: `@modelcontextprotocol/sdk@^1.12.0`).
- **Registers all 34 Mecris tools** as native Pi tools (`mecris_` prefix), converting each tool's MCP JSON-Schema input into a **TypeBox schema** so Pi validates arguments the same way it validates its built-in `read`/`bash`/`edit` tools.
- **Lazy-loads for token efficiency** (mirrors `py_harness`'s `filter_core_tools`):
  - 5 read-only status tools active at startup: `get_narrator_context`, `get_beeminder_status`, `get_budget_status`, `get_daily_aggregate_status`, `get_system_health`.
  - Other ~29 write/admin tools are deferred behind a `mecris_load_tools` loader tool.
  - Configurable via `MECRIS_CORE_TOOLS` env var.
- **Adds commands:**
  - `/mecris [focus]` — one-shot status update ("in the normal way").
  - `/mecris-reconnect` — restart the bridge without a full `/reload`.
- **Lifecycle management:** Cleans up the subprocess on `session_shutdown`.

### 2. Key Architectural Decision: Use `mcp_stdio_server.py`, not `mcp_server.py --stdio`
**Why this matters:** All existing harness configs (Claude Code, Gemini, Antigravity) launch `mcp_server.py --stdio`, which **also binds FastAPI on port 8080** for the Android bridge. Running two instances at once **hard-fails on the bound port**. I followed the native `py_harness` and used `mcp_stdio_server.py` (scheduler + stdio **only**, no HTTP bridge) so **Pi coexists peacefully with any other running harness**.

### 3. End-to-End Verification (Not Mocked)
- **Connection test:** MCP server connected in 2.7 seconds, listed 34 tools cleanly.
- **Live model call:** `claude-haiku-4.5` via GitHub Copilot called `mecris_get_narrator_context` and summarized:
  > *"5 active goals, 13 days budget remaining, you're 1/3 on today's daily goals—urgent: daily walk + Greek reviews. All Beeminder goals safe from derailment."*
  - This was **real data from Neon DB** (live goal state, not mock).
- **Deferred tool path:** Model called `mecris_load_tools` (activation), then `mecris_get_recent_usage` (deferred tool), and returned **real usage rows** (10 sessions, costs, timestamps).
- **Known issue:** `groq/gpt-oss-20b` failed on tool-call arg JSON serialization ("Failed to parse tool call arguments") — that's a Groq model-side issue, not the bridge. Copilot models handled it cleanly.

### 4. Project Setup
- Created `.pi/extensions/mecris/` as a project-local Pi extension (auto-discovered after trust prompt).
- `npm install` installs the MCP SDK into `node_modules/`; `.gitignore` keeps it out of the repo while preserving `package.json`/`package-lock.json`.
- Configuration via env vars:
  - `MECRIS_HOME` (default: repo root, 3 levels up)
  - `MECRIS_PYTHON` (default: repo `.venv/bin/python`)
  - `MECRIS_STDIO_SCRIPT` (default: `mcp_stdio_server.py`)
  - `MECRIS_CORE_TOOLS` (default: 5 status tools)

## Parity Matrix: All Five Harnesses

| Capability | Claude Code | Gemini CLI | Antigravity CLI | `py_harness` | **Pi bridge** |
|---|---|---|---|---|---|
| Config format | `.mcp.json` | `.gemini/settings.json` | `~/.gemini/antigravity-cli/mcp_config.json` | Python params | `.pi/extensions/mecris/` (TS) |
| Server entrypoint | `mcp_server.py --stdio` | `mcp_server.py --stdio` | `mcp_server.py --stdio` | `mcp_stdio_server.py` | `mcp_stdio_server.py` |
| Binds port 8080 | ⚠️ yes | ⚠️ yes | ⚠️ yes | ✅ **no** | ✅ **no** |
| Tool transport | MCP stdio | MCP stdio | MCP stdio | MCP stdio | MCP stdio |
| Lazy loading | ❌ all active | ❌ all active | ❌ all active | ✅ 1 core tool | ✅ core set + loader |
| Backend model | Claude | Gemini | Gemini | Ollama local | any Pi provider |
| Native tool calls | ✅ | ✅ | ✅ | optional (fallback) | ✅ |
| Open-source harness | ❌ | ❌ | ❌ | ✅ (yours) | ✅ |

## Differences vs the Native `py_harness/`

Both bridge Mecris, but they're built for different use cases:

| Aspect | `py_harness/` | Pi bridge |
|---|---|---|
| **Loop** | Hand-rolled `run_loop` in `mecris_harness.py` | Pi's general-purpose agent loop |
| **Model** | Ollama/Hailo edge (`gemma4`, `qwen2:1.5b`) | Any Pi provider (GitHub Copilot, Groq, Anthropic, Google, …) |
| **Core tool set** | exactly `get_narrator_context` (1 tool) | 5 read-only status tools + loader |
| **Prompt-based tool fallback** | ✅ for models without native tool support | not needed (Pi handles serialization) |
| **`get_narrator_context` output pruning** | ✅ hard-coded for NPU cache limits | ❌ not yet (big-context models don't saturate like Hailo does) |
| **Caveman/RTK compression persona** | ✅ system prompt ("Brain big, mouth small") | ❌ not ported yet |
| **History pruning** | `prune_history`: system + last 20 messages | Pi's own compaction algorithm |

## Strategic Insights

1. **Pi is the first vendor-agnostic Mecris harness.** Claude Code, Gemini, Antigravity all lock you to their parent company's models. With Pi, you drive Mecris with any backend (Copilot, Groq, Anthropic, Google, OpenAI, or a custom proxy). You own the harness and the flow.

2. **The port-8080 conflict was real and subtle.** All the existing configs cause hard port failures when run in parallel. This is the first harness design that lets you run multiple agents talking to Mecris simultaneously — essential for failover and testing.

3. **Schema conversion was the gnarly bit.** MCP's JSON-Schema `inputSchema` is slightly different from TypeBox's Schema type (TypeBox adds internal `[Kind]` symbols for its Value checker). I wrote a recursive converter that handles the common cases (strings, ints, booleans, optional fields, arrays, nested objects) and falls back gracefully. It's ~60 lines and handles all 34 Mecris tools.

4. **Lazy loading via a model-callable loader is elegant.** Instead of forcing you to enable all 34 tools upfront (token bloat), the model calls `mecris_load_tools` to activate what it needs. Pi's native deferred-tool API makes this trivial and cache-friendly.

## Known Issues & Workarounds

- **Groq `gpt-oss-20b` tool serialization bug:** Model fails to emit valid JSON for optional parameters. Workaround: use a different provider (GitHub Copilot, Anthropic, Google all work). Root cause: likely a Groq model-side limitation, not the bridge.
- **Project trust prompt:** First run requires you to accept a project-trust dialog (Pi security policy). After that, the extension auto-loads.

## Roadmap

### Now — v0.0.1 (done) ✅
- [x] MCP stdio bridge, 34 tools, JSON-Schema → TypeBox conversion.
- [x] Lazy loading via `mecris_load_tools`.
- [x] `/mecris` and `/mecris-reconnect` commands.
- [x] Clean subprocess lifecycle on shutdown.

### Next — v0.1.0 (parity polish) 📝
- [ ] **Caveman persona parity:** ship an `--append-system-prompt` snippet that mirrors the `py_harness` "Brain big, mouth small" narrator so the voice matches across harnesses.
- [ ] **Narrator-context pruning option:** port the defensive `get_narrator_context` payload pruning (bookmarks, walk details, system pulse) behind an env flag for small local models.
- [ ] **Result rendering:** implement `renderResult` so Mecris tool output shows as a compact card in the Pi TUI instead of raw JSON.
- [ ] **Package it:** publish as a pi package (`pi install git:github.com/kingdonb/mecris`) so it installs without the local `.pi/extensions` copy.
- [ ] **Skill bridge:** expose the four Gall-loop skills (`/mecris-orient`, `/mecris-plan`, `/mecris-archive`, `/mecris-pr-test`) as Pi skills or commands.

### Later — v0.2.0 (harness-native features) 🚀
- [ ] **Auto-status on session start:** optional `session_start` turn that greets you with your runway/budget (opt-in; respects quiet hours).
- [ ] **Groq odometer hook:** record Pi's own Groq token usage back into Mecris via `record_groq_reading` using Pi's `after_provider_response` event.
- [ ] **Budget governor gate:** a `tool_call`/`before_provider_request` guard that warns/blocks when `get_budget_governor_status` says the budget is spent.
- [ ] **Local-first mode:** wire Pi's custom-provider API to the Hailo-ollama edge node so Pi can run the same local model as `py_harness` when offline.

### Open questions for later
- Should Mecris ship a canonical harness config generator (`mecris init <harness>`) that writes the right config for Claude Code / Gemini / Antigravity / Pi from a single source of truth? Would kill config drift.
- Revive the cloud Spin/WASM backend (offline since ~April 2026) so the Pi bridge can failover to the cloud hub like the Android app does.

## Files Changed

- `.pi/extensions/mecris/index.ts` — the bridge extension (~350 lines)
- `.pi/extensions/mecris/package.json` — MCP SDK dependency
- `.pi/extensions/mecris/package-lock.json` — locked versions
- `.pi/extensions/mecris/README.md` — extension documentation
- `.pi/extensions/mecris/.gitignore` — exclude node_modules
- `docs/PI_HARNESS_ROADMAP.md` — full parity analysis and roadmap

## To Use

1. **One-time setup:**
   ```bash
   cd .pi/extensions/mecris && npm install
   ```

2. **Auto-discovery (trust the project once):**
   ```bash
   pi  # You'll get a project-trust prompt, accept it
   ```

3. **Or explicit load (for testing):**
   ```bash
   pi -e ./.pi/extensions/mecris/index.ts --provider github-copilot --model claude-haiku-4.5
   ```

4. **In the chat:**
   - Ask for a status update naturally: *"What's my Mecris status?"*
   - Use `/mecris` for a one-shot.
   - Non-core tools activate via `mecris_load_tools` (the model calls it automatically).

## Next Steps

- [ ] Test the bridge against all configured Pi providers (Groq, Anthropic, Google).
- [ ] Port the Caveman persona system prompt for voice parity.
- [ ] Verify the lazy-loading UX (does the model naturally call the loader?).
- [ ] Publish as a pi package so users don't need `.pi/extensions/` scaffolding.
- [ ] Consider adding a `on("before_provider_request")` hook to warn if budget is low.
- [ ] Revisit the cloud Spin/WASM failover path once cloud hosting is restored.

---

# Session Log: 2026-07-02 (Local WASM API Verification & CLI Diagnostics)

## Context
- **Date**: Thursday, July 2, 2026 (Local)
- **Status**: Verified local Spin WASM build and local service API. Ran full Python and Rust test suites successfully. Checked CLI diagnostics and presence/nagging engine state.
- **Narrator**: Antigravity (Gemini)

## Accomplishments
1. **CLI Engine Diagnostics**:
   - Ran `mecris pulse` and verified high-density status report, leader election status (MCP local server active and elected leader), and goal runways.
   - Ran `mecris nag eval` and confirmed that the nagging quiet hours logic correctly stood down (no message sent during sleep window 8 PM - 8 AM).
   - Ran `mecris presence check` confirming no human presence lock exists at `/tmp/mecris_presence.lock`.
2. **WASM API Build & Rust Testing**:
   - Built the Spin WASM components successfully via `make build-wasm`.
   - Verified the Rust test suite using `make test-rust` (**28 tests passed successfully**).
3. **Full Integration Testing**:
   - Booted the local Spin development server (`make run-local` on port 3000) using local `.env` variables.
   - Executed the complete Python test suite via `make test-python` and confirmed that all **1488 tests passed** successfully.
   - Cleaned up local test server tasks to ensure a tidy workspace.

## Strategic Insights & Issues Raised
- **WASM API Local Integrity**: The local Rust/Spin API compiled easily and passed all contract/E2E integration tests, meaning the underlying engine is ready for deployment.
- **Cloud Drift / Ghost Heartbeat**: The Fermyon and Akamai cloud deployments have been offline since April/May 2026, causing the "Ghost Heartbeat" to be silent for 50+ hours. Redeploying the Spin API is key to reviving the cloud cron and failover nagging.
- **CI/CD Requirement**: Running the test suites locally is slow and manual. Building automated PR CI will allow continuous verification of all 1500+ tests on every PR branch before merge.

## Next Steps
- [ ] Build GitHub Actions CI workflow to run full Python & Rust tests on pull request approval.
- [ ] Investigate Android widget discrepancies (Arabic cake progress / top 3x goal status out of sync).
- [ ] Finalize Spin API hosting plans on the `Beby.cloud` Kubernetes Tailnet cluster.

---

# Session Log: 2026-06-29 (Android Widget Inconsistencies & Python MCP Latency)

## Context
- **Date**: Monday, June 29, 2026 (Local)
- **Status**: Verified live Android sync via Python MCP server. Raised widget inconsistency and sync latency issues.
- **Narrator**: Mecris (Gemini)

## Accomplishments
1. **Direct MCP Verification**: Verified that the Antigravity CLI successfully invokes lazy-loaded MCP tools (e.g., `get_narrator_context`) directly via the MCP server bridge without manual Python script calls.
2. **Android Sync Success**: Confirmed Android app successfully completed a "Cloud Sync" via the local Python MCP server (`10.17.14.155:8080`), updating Android Client status to "🟢 Healthy" (seen 1m ago).
3. **Runway Dispatches**: Dispatched the `reviewstack` goal and verified Greek goal progress, updating system metrics.

## Strategic Insights & Issues Raised
- **Android App Widget Discrepancies**:
  - The Arabic goal is marked met in the main Android app, but the "cake progress" widget displays it as unmet.
  - Greek completions are done, but the 3x header widgets at the top of the Android app do not reflect this progress.
- **Python MCP API Latency**:
  - The syncing process over the Python MCP API is noticeably slower than the Rust/Spin API.
  - The Spin API is battle-hardened and better tested but remains down due to broken hosting configurations on Akamai/Fermyon.
  - Re-hosting the Spin API on the Beby.cloud Kubernetes cluster remains the primary pathway for high-performance syncs.

## Next Steps
- [ ] Research and resolve the Android app widget mismatch (Arabic cake progress and 3x goal widgets at the top).
- [ ] Plan and execute Spin API re-hosting on the Beby.cloud Kubernetes cluster.
- [ ] Fix terminal console emoji rendering issues.
- [ ] Integrate stdout token streaming in the local AI loop (`mecris_harness.py`).

---

# Session Log: 2026-06-28 (Local AI Edge Loop & Port Conflict Fixes)

## Context
- **Date**: Sunday, June 28, 2026 (Local)
- **Status**: Verified local Python harness talking to remote Hailo-ollama node via prompt-based ReAct loop.
- **Narrator**: Mecris (Gemini)

## Accomplishments
1. **Local AI Edge Integration**:
   - Connected the Python harness (`MecrisHarness`) to the remote Hailo-ollama server (`192.168.2.109:30434`) running `qwen2:1.5b` (HEF format).
   - Created `OllamaClient` configuration bypass (`use_native_tools=False`) to avoid Oat++ JSON mapping crashes on standard tools array schemas.
2. **Textual Tool Call Parsing**:
   - Implemented a case-insensitive standalone word matcher (`\bget_narrator_context\b`) and a substring JSON extractor to reliably parse model outputs (e.g. bare `Get_narrator_context` text).
3. **Telemetry & Payload Pruning**:
   - Integrated payload pruning for `get_narrator_context` output (stripping bookmarks, daily walk details, and system pulse metadata). This reduced the message payload from 8.4 KB to 2.3 KB, preventing NPU cache saturation and 502 Bad Gateway timeouts.
4. **Stdio Event Loop & Port Deadlock Fixes**:
   - Modified `mcp_stdio_server.py` to run asynchronously under `asyncio.run()`, resolving event loop crashes when launching the coordination engine, and preventing uvicorn port conflicts on `8080`.
5. **Live Stream Demonstration**:
   - Successfully ran the harness during the live stream, executing a tool call, reading the live Neon database context, and generating a caveman goals status report.
6. **Harness Robustness Tests & Identity Hardening (Post-Stream)**:
   - Authored **[tests/test_harness_react_robustness.py](file:///Users/yebyen/w/mecris/tests/test_harness_react_robustness.py)** to verify the prompt-based ReAct loop against mixed text/JSON formats, bare capitalized tokens, and Chinese/bilingual context triggers.
   - Refactored system instructions in **[py_harness/main.py](file:///Users/yebyen/w/mecris/py_harness/main.py)** to explicitly separate agent (`Mecris`) and user (`Kingdon`) name mappings.

## Strategic Insights
- **Constrained hardware requires prompt constraints.** Large token contexts (like an 8 KB JSON payload) saturate local NPU caches and cause inference timeouts. Defensive pruning keeps response times under 3 seconds on the Hailo 10H.
- **Payload mapping must align with C++ DTOs.** Simple Ollama C++ server wrappers can fail on standard tools arrays. Prompt-based schema injection is a robust, universal fallback for edge LLMs.

## Next Steps
- [x] **Mecris Identity Alignment**: Resolve identity confusion by injecting clear User/Agent names into system prompt parameters.
- [ ] **Verify Naming Fix Live**: Run the updated main harness against the Qwen2 1.5B edge node to verify that it addresses the user as Kingdon.
- [ ] **Console UI Polishing**: Address rough emoji rendering (`🎈`, `🗑`, etc.) in the terminal.
- [ ] **Token Streaming**: Implement stdout streaming in `run_loop` to eliminate black-box wait times.
- [ ] **Kubernetes Hosting**: Finalize sync-service deployment manifests on the Tailnet cluster.

---

# Session Log: 2026-06-28 (Antigravity MCP Integration & Security Hardening)

## Context
- **Date**: Sunday, June 28, 2026 (Local)
- **Status**: Antigravity CLI connected to local Mecris MCP server. Secure config.
- **Narrator**: Mecris (Gemini)

## Accomplishments
1. **Antigravity CLI MCP Integration**:
   - Connected the Antigravity CLI (`agy`) to the local Mecris MCP server by configuring `~/.gemini/antigravity-cli/mcp_config.json`.
2. **Security Hardening**:
   - Kept all sensitive database credentials, API keys, and auth tokens out of the global configuration file.
   - Refactored `mcp_server.py` to resolve its `.env` path dynamically via `os.path.abspath(__file__)`, allowing it to load the workspace `.env` file securely without copying secrets into the system-level config file.
3. **Android Sync & Walk Status**:
   - Verified that the Android app's "Cloud Sync" successfully uploads data, resolving sync delays and returning status cleanly.
   - User walk today (0.60 miles) was completed and logged.

## Strategic Insights
- **Secrets stay local.** Duplicating secrets to external files (like `mcp_config.json` in the home directory) introduces risk and violates the single source of truth model. Keeping all environment variables in `.env` and loading it relative to the script location maintains clean separation.
- **Tailnet Deployment is the future.** The local sync bridge shows Tailnet-Native operations are highly stable. Migrating permanently to a local Kubernetes deployment is the next logical step.

## Next Steps
- [ ] Investigate deployment to the new 9-node HA Kubernetes cluster on the Tailnet.
- [ ] Evaluate the local AI model capabilities using the Hailo AI device (low contact size models).
- [ ] Investigate integration obstacles with Tab Maestro and evaluate if Mecris can fit.
- [ ] Address review pump target values and streaming API integration.

---

# Session Log: 2026-06-11 (Local Bridge & Non-Blocking Milestone)

## Context
- **Date**: Wednesday, June 10, 2026 (Local) / Thursday, June 11, 2026 (UTC)
- **Status**: Android-to-Local link restored. Blocking sync bottlenecks eliminated.
- **Narrator**: Mecris (Gemini)

## Accomplishments
1. **Local Bridge Restoration**:
   - Refactored `mcp_server.py` to support **concurrent stdio/HTTP bridges**. The HTTP bridge (Port 8080) now runs in a background thread by default.
   - Restored communication between the Android app and the local leader via LAN (`10.17.14.155:8080`).
   - Verified "Success" in the Android UI and confirmed data flow to Beeminder (`reviewstack`).
2. **Non-Blocking Architecture**:
   - Eliminated the 30-second "Fetching" hang by decoupling Clozemaster scraping from HTTP fetch requests.
   - Implemented a "Fast Fetch" pattern: return cached Neon stats instantly and trigger background sync tasks.
   - Wrapped all synchronous `psycopg2` and credential-loading logic in `asyncio.to_thread` to prevent event loop hijacking.
3. **Android Flexibility & Resilience**:
   - Updated `BackendManager.kt` with a dedicated **"Local (Python: 8080)"** selector.
   - Added a **Tailnet (Tailscale)** configuration path to support remote sync without public cloud infrastructure.
   - Expanded `network_security_config.xml` whitelists to permit Tailscale and broader LAN ranges.
4. **Maintenance & Budget**:
   - Recorded May month-end and June initial budget readings for Groq ($19.89 remaining).
   - Resolved the "phantom method" bug: implemented missing `_update_heartbeat` in `MecrisScheduler`.

## Strategic Insights
- **The "Brain" must never stop the "Heart".** Heavy background tasks (scrapers) must be strictly non-blocking to keep the networking stack responsive to mobile clients.
- **Tailscale is the primary fallback for Cloud.** When Spin/Fermyon/Akamai versioning is in flux, the Tailnet-Native Sync Bridge provides production-grade reliability on consumer hardware.
- **Port 8080 is the new default for local Android sync.** This separates the "Android Bridge" from other local services and minimizes conflict.

## Next Steps
- [ ] Complete the **Talos Linux** image build for the Pi cluster.
- [ ] Deploy the `sync-service` as a **Spintainer** on the new cluster.
- [ ] Investigate the "Moussaka Nag" logic to ensure it doesn't trigger erroneously during the cloud-to-local transition.
- [ ] Finalize and merge PR **#260**.

---
*Followed by previous logs...*

# Session Log: 2026-06-06 (Token Efficiency & Local-First Milestone)
... [Previous Content] ...
