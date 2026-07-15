# Getting Started with Mecris (From Zero)

> A first-run guide for new users. Assumes **nothing** — no `.env`, no database,
> no API keys. By the end you'll have a working Mecris and an agent talking to it.

If you already have a configured `.env`, skip to [docs/QUICK_START.md](QUICK_START.md)
to pick an agent harness.

---

## 0. What you're setting up

Mecris is a personal accountability system. An LLM agent ("narrator") reads your
goals, budget, and activity from a database and nags you constructively. The
minimum viable setup is:

1. **A PostgreSQL database** (the single source of truth — required)
2. **A `.env` file** (configuration — required)
3. **An agent harness** (Pi, py_harness, Claude Code, Gemini — pick one)

Everything else (Beeminder, Twilio SMS, weather, language learning sync) is an
**optional integration** you can add later. Mecris degrades gracefully: tools
for integrations you haven't configured will report as unavailable rather
than crash.

## 1. Prerequisites

| Tool | Why | Install |
|---|---|---|
| Python 3.13+ | The MCP server | `brew install python` or pyenv |
| `uv` | Python dependency management | `brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js 20+ | Only if using the Pi harness | `brew install node` |
| A PostgreSQL database | Central state | See step 3 — free options exist |

```bash
git clone https://github.com/kingdonb/mecris.git
cd mecris
uv venv
uv pip install -r requirements.txt
```

## 2. Create your `.env`

There is no `.env` in a fresh clone — copy the example and edit it:

```bash
cp .env.example .env
```

Only **one** variable is truly required to boot: `NEON_DB_URL`. The usage
tracker will refuse to start without it:

> `NEON_DB_URL must be set. SQLite fallback is no longer supported.`

Leave everything else at defaults for now. A minimal working `.env`:

```bash
MECRIS_MODE=standalone          # trusted single-user mode, no OIDC needed
NEON_DB_URL="postgresql://user:pass@host/dbname"   # from step 3
REMINDER_DELIVERY_METHOD=console  # print nags to console; no Twilio needed
REMINDER_TEST_MODE=true           # keep messages local while you set up
LOG_LEVEL=INFO
```

**`MECRIS_MODE=standalone`** is the default and what you want as a new user:
it trusts local connections and maps everything to a single default user. The
`multi-tenant` mode (JWT + Pocket ID OIDC) is for hosted deployments — ignore
it until you need it (see [docs/AUTH_CONFIGURATION.md](AUTH_CONFIGURATION.md)).

## 3. Get a database (pick one)

### Option A: Neon free tier (recommended, ~2 minutes)

1. Sign up at [neon.tech](https://neon.tech) (free tier is plenty)
2. Create a project; copy the connection string it shows you
3. Paste it into `.env` as `NEON_DB_URL`

Neon is what Mecris is built against ("Neon DB" appears throughout the docs),
and the free tier's autosuspend behavior is fine for personal use.

### Option B: Local PostgreSQL via Docker (fully offline)

```bash
docker run -d --name mecris-db \
  -e POSTGRES_DB=mecrisdb \
  -e POSTGRES_USER=mecris \
  -e POSTGRES_PASSWORD=mecris \
  -p 5432:5432 \
  postgres:16
```

Then in `.env`:

```bash
NEON_DB_URL="postgresql://mecris:mecris@localhost:5432/mecrisdb"
```

Any PostgreSQL 14+ works — "Neon" in the variable name is historical.

### Initialize the schema

Either way, create the tables:

```bash
PYTHONPATH=. .venv/bin/python scripts/initialize_neon.py
```

This is idempotent — safe to re-run. (The CI workflows do exactly this against
a throwaway Postgres, so it's well-exercised.)

## 4. Smoke test the server

```bash
PYTHONPATH=. .venv/bin/python mcp_stdio_server.py
# It should start, log scheduler election, and wait on stdin.
# Ctrl-C to exit. Startup errors will name the missing config.
```

If that starts cleanly, your database and `.env` are good. Logs go to
`/tmp/mecris_stdio.log` if you need to dig.

## 5. Connect an agent (pick one path)

Full comparison: [docs/QUICK_START.md](QUICK_START.md). The short version:

### Pi (bring your own model — recommended for trying Mecris)

```bash
cd .pi/extensions/mecris && npm install && cd ../../..
pi           # accept the project-trust prompt on first run
```

Then just ask: *"What's my Mecris status?"* — or use `/mecris`.
Details: [docs/PI_MECRIS_GUIDE.md](PI_MECRIS_GUIDE.md)

### py_harness (local Ollama, fully offline)

```bash
PYTHONPATH=. .venv/bin/python3 py_harness/main.py
```

### Claude Code / Gemini CLI

Configs are already in the repo (`.mcp.json`, `.gemini/settings.json`) — open
the project in your tool and the `mecris` MCP server is picked up automatically.

## 6. Your first data

A fresh database means the narrator has nothing to narrate. Seed it:

**With Beeminder (the primary integration):** add to `.env`:

```bash
BEEMINDER_USERNAME=your_username
BEEMINDER_AUTH_TOKEN=your_token   # from https://www.beeminder.com/api/v1/auth_token.json
```

Restart your harness and ask for a status — your Beeminder goals, runway, and
derail risks appear immediately (they're fetched live).

**Without Beeminder:** you can still use goals and todos stored in Mecris
itself. Ask your agent:

> "Add a goal for me: walk 2000 steps daily" (uses `add_goal`)

**Budget tracking (optional):** if you use Claude/Anthropic, set
`CLAUDE_API_KEY` and `CLAUDE_BUDGET_LIMIT` in `.env` to get burn-rate tracking
and the "days remaining" runway in every status report.

## 7. Optional integrations (add whenever)

| Integration | `.env` variables | What it unlocks |
|---|---|---|
| Beeminder | `BEEMINDER_USERNAME`, `BEEMINDER_AUTH_TOKEN` | Goal portfolio, runway, derail alerts |
| Twilio SMS/WhatsApp | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_TO_NUMBER` | Real nags on your phone (set `REMINDER_DELIVERY_METHOD=sms`) |
| Anthropic budget | `CLAUDE_API_KEY`, `CLAUDE_BUDGET_LIMIT` | Real-time spend tracking via Admin API |
| Obsidian | `OBSIDIAN_VAULT_PATH` + Obsidian MCP | Notes/todos as narrator context |
| Weather | (cloud/Spin config) | "Walk now, rain later" heuristics |

Until configured, the related tools simply report the integration as
unavailable. Start with `REMINDER_DELIVERY_METHOD=console` and
`REMINDER_TEST_MODE=true` so nothing texts anyone while you experiment.

## 8. Verify everything

```bash
# The narrator can see your world:
pi --no-session -p "Call mecris_get_narrator_context and give me a one-line status."

# Sanity test suite (fast, no external services needed):
PYTHONPATH=. .venv/bin/pytest tests/test_pi_bridge_sanity.py -q
```

## Troubleshooting first-run issues

| Error | Cause | Fix |
|---|---|---|
| `NEON_DB_URL must be set` | No `.env` or missing variable | Steps 2–3 above |
| `connection refused` on DB | Postgres not running / wrong URL | Check `docker ps` or the Neon console |
| `relation ... does not exist` | Schema not initialized | Run `scripts/initialize_neon.py` |
| Beeminder tools return errors | No Beeminder credentials | Optional — add them, or ignore those tools |
| No nags arriving | Console mode (by design) | Set `REMINDER_DELIVERY_METHOD=sms` + Twilio vars when ready |
| Pi: "bridge offline" | Extension deps not installed | `npm install` in `.pi/extensions/mecris/` |

## Where to go next

- [docs/QUICK_START.md](QUICK_START.md) — harness comparison and daily use
- [docs/PI_MECRIS_GUIDE.md](PI_MECRIS_GUIDE.md) — Pi harness deep dive
- [docs/SETUP_GUIDE.md](SETUP_GUIDE.md) — agent config file reference (Claude Desktop, Gemini, `.mcp.json`)
- [docs/AUTH_CONFIGURATION.md](AUTH_CONFIGURATION.md) — multi-tenant/OIDC mode
- [ARCHITECTURE.md](../ARCHITECTURE.md) — how the pieces fit together

Welcome aboard. The forest remembers every missed step — but it's patient with
new hikers. 🐗
