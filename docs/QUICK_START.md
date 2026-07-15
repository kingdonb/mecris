# Mecris Quick Start Guide

> Get Mecris running with your preferred agent harness in 5 minutes.

**Choose your path:**

## 🦑 Path 1: Pi (Multi-Model, Vendor-Agnostic)

Best for: GitHub Copilot, Groq, Anthropic, Google, local models. Bring your own.

```bash
# 1. Install dependencies (one time)
cd .pi/extensions/mecris
npm install
cd ../../..

# 2. Trust the project (security prompt, one time)
pi

# 3. Ask for a status update naturally
> What's my Mecris status?
> How many days of budget left?
> What's urgent today?
```

**Features:**
- ✅ Any Pi provider (Copilot, Groq, Anthropic, Google, local Ollama)
- ✅ Token-efficient lazy-loading (5 core tools at startup)
- ✅ `/mecris` command for one-shot status
- ✅ Full 34-tool access via `mecris_load_tools`

**Learn more:** [docs/PI_MECRIS_GUIDE.md](docs/PI_MECRIS_GUIDE.md)

---

## 🏃 Path 2: py_harness (Local-First, Ultra-Efficient)

Best for: Speed, privacy, local-only Ollama inference on your machine.

```bash
# 1. Install dependencies (one time)
uv venv
uv pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your Beeminder, Twilio, Neon credentials

# 3. Launch the harness
PYTHONPATH=. .venv/bin/python3 py_harness/main.py
```

**Features:**
- ✅ Local Ollama (Gemma 4, Qwen 1.5B)
- ✅ Ultra-minimal context (1.5k overhead)
- ✅ Works offline after first sync
- ✅ Caveman "brain big, mouth small" persona
- ✅ Defensive payload pruning for edge NPUs

**Learn more:** [py_harness/README.md](py_harness/README.md)

---

## 🌐 Path 3: Cloud Harnesses (Vendor-Locked, Simple Setup)

Best for: One-click setup with a single provider (Claude, Gemini, etc.).

### Claude Code

```bash
# Configure .mcp.json (already present)
# Make sure your Claude Code IDE extension is installed
# Tools will be available in Claude's context automatically
```

**Learn more:** [.mcp.json](.mcp.json)

### Gemini CLI / Antigravity

```bash
# Configure .gemini/settings.json or ~/.gemini/antigravity-cli/mcp_config.json
# Launch your Gemini terminal
# Mecris tools will be available in Gemini's context
```

**Learn more:** [.gemini/settings.json](.gemini/settings.json)

---

## ✅ Verify It Works

### Pi
```bash
pi -e ./.pi/extensions/mecris/index.ts --no-session \
  -p "Call mecris_get_narrator_context and give me a one-line status"
```

Expected output: *"5 active goals, 13 days budget left, 1/3 daily score — urgent: walk + Greek reviews"*

### py_harness
```bash
# After launching, you should see:
# > Narrator ready. What would you like to know about your goals?
# Type: What's my status today?
```

Expected output: Status summary from your live Beeminder/budget data.

### Cloud Harnesses
Open your IDE (Claude Code) or terminal (Gemini/Antigravity) and ask:
*"What's my Mecris status?"*

---

## Common Questions

**Q: Which harness should I use?**

| Use Case | Harness |
|---|---|
| "I want to try Mecris quickly" | Pi (fastest setup) |
| "I work offline and need privacy" | py_harness (local-first) |
| "I already use Claude Code" | Claude Code (IDE integration) |
| "I already use Gemini/Antigravity" | Gemini CLI or Antigravity |

**Q: Can I run multiple harnesses at once?**

Yes! They all connect to the same Neon database:
- py_harness on :8000 uses `mcp_stdio_server.py` (stdio only)
- Claude Code uses `.mcp.json` config (stdio only)
- Gemini uses `.gemini/settings.json` (stdio only)
- Pi uses `.pi/extensions/mecris/` (stdio only)

Each spawns its own MCP server subprocess; they coordinate via the database. Only the Android bridge (`mcp_server.py --stdio` on :8080) can't run in parallel with others (port conflict). Use local Python harness for that.

**Q: How do I see available tools?**

In Pi:
```
> What tools can you call to help me with Mecris?
> Show me the list of available commands.
```

In py_harness:
```bash
# Check the MCP server's tool registry
curl http://127.0.0.1:8000/tools
```

In Claude Code / Gemini:
Just ask! The tools are in context automatically.

**Q: How do I customize the behavior?**

**Pi:** Edit `.pi/extensions/mecris/index.ts` and run `/reload`

**py_harness:** Edit `py_harness/main.py` and restart

**Claude Code / Gemini:** Configure via `.mcp.json` or `.gemini/settings.json`

**Q: What if something breaks?**

**Pi:**
- Try `/mecris-reconnect` to restart the bridge
- Check logs: `tail -f /tmp/mecris_stdio.log`
- Verify venv: `.venv/bin/python mcp_stdio_server.py` (should start without errors)

**py_harness:**
- Check `.env` is configured correctly
- Verify Neon connection: `psql $NEON_DB_URL` (should connect)
- See `py_harness/main.py` for logs

**Claude Code / Gemini:**
- Verify `.mcp.json` or `.gemini/settings.json` is valid JSON
- Check that `mcp_server.py --stdio` runs without errors

---

## Architecture

All harnesses connect to the same **Neon PostgreSQL database** (the source of truth):

```
       Pi Bridge          py_harness          Claude Code
         (TS)            (Python)              (IDE Extension)
           |                 |                       |
           ├─ MCP Stdio ─────┴─────────────────────┐
           |                                         |
           └────────── NEON DB ────────────────────┘
                   (Central State)
```

Updates from any harness are immediately visible to all others (they read/write the same database).

---

## Next Steps

1. **Pick a harness** (above)
2. **Follow setup** for your harness
3. **Run verification** (above)
4. **Read docs** for your harness:
   - Pi: [docs/PI_MECRIS_GUIDE.md](docs/PI_MECRIS_GUIDE.md)
   - py_harness: [py_harness/README.md](py_harness/README.md)
   - Harness comparison: [docs/PI_HARNESS_ROADMAP.md](docs/PI_HARNESS_ROADMAP.md)
5. **Ask for help** in your harness's chat/terminal

---

## Status

| Harness | Status | Maintained |
|---|---|---|
| py_harness | ✅ Active | Kingdon (you) |
| Pi | ✅ Active | Claude Opus + Pi team |
| Claude Code | ✅ Active | Anthropic |
| Gemini CLI | ✅ Active | Google |
| Antigravity CLI | ✅ Active | Community |
| Android Go | ⚠️ Offline | Needs cloud rehosting |

---

**Everything clear? Pick a path above and get started!** 🚀
