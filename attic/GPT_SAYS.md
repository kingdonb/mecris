You're doing a great job surfacing the tech debt early—and that’s what keeps ambitious systems from crumbling under their own cleverness. Let’s break this down cleanly into prioritized, actionable instructions Claude can follow, and where you might step in directly for setup or architecture adjustments.

---

### ✅ Claude Task List (Structured for Iteration)

---

#### (1) **Fix: MCP Server Management Issues**

**Problems:**

* Claude starts `python3` instead of the venv Python → leads to missing packages.
* MCP server left running after session.
* No health check; waits \~2m blindly.
* No authentication, bound to `0.0.0.0` → potential public exposure.

**What Claude Should Do:**

* 🔧 Add a **`/health` endpoint** that returns `200 OK` once the server is ready.
* 🛡️ Add **basic auth** or localhost-only binding (`127.0.0.1`) in `uvicorn` or FastAPI.
* ✅ Ensure all `start_server.py` commands reference the venv python binary (`sys.executable`).
* 💡Create `launch_server()` and `shutdown_server()` scripts or wrappers (shell or Python).

  * `launch_server.sh` → spawns MCP in a new tmux or subprocess with trap cleanup.
  * `shutdown_server.sh` → gracefully kills MCP with PID file or health check timeout.

**What You Can Do Right Now:**

```bash
# Sample safe launch command inside tmux or venv
source .venv/bin/activate
tmux new-session -d -s mcp './start_server.py'

# Ensure it's binding only to localhost!
uvicorn mcp_server:app --host 127.0.0.1 --port 8000
```

---

#### (2) **Bug: Beeminder Data Incorrect**

**Problems:**

* Read-only mode confirmed ✅
* But live data is either wrong or stale
* Mocked goals/graphs may still be in use

**What Claude Should Do:**

* 🧪 Write integration test: `test_fetch_beeminder_goals_live()`
* 🕵️ Audit code for any static JSON or mock files in use during `/narrator/context`
* 🔍 Confirm token is passed correctly, and that **`username` isn't hardcoded**

**Nice to Have:**

* Show date/time of last Beeminder API poll in status dashboard
* Add optional `--live` and `--mock` flags to boot server with or without mocks

---

#### (3) **Broken: Claude API Credit Tracking**

**Problems:**

* Budget tracker reports wrong values
* Balance lookup likely mocked or hardcoded
* Claude claims there's no way to query balance programmatically

**What Claude Should Do:**

* 🧪 Point out: “There is no *public* Claude API billing endpoint.”
* 🧭 Instead, write scraper logic for this URL:
  `https://console.anthropic.com/settings/billing` (requires login session)

**Your Role:**

* Use something like `puppeteer` or `playwright` to automate login + balance scrape
* Claude can help generate this code (securely handles credentials from `.env`)
* Until then: **mock this with a manual update mechanism**, e.g., `budget.json`

---

#### (4) **Refactor: Docs & Project Structure**

**Problems:**

* Every Claude session re-ingests redundant or scattered context
* Too many scratchpad files and logs
* CLAUDE.md and README are both outdated and redundant
* Mocks are undocumented in the codebase

**What Claude Should Do:**

* 📚 Curate `README.md` for:

  * Quickstart instructions
  * MCP lifecycle commands
  * Endpoints and known mock areas
* 📖 Revise `CLAUDE.md` into a minimal bootloader guide: *“What you must know before continuing work”*
* 🧼 Move all log/scratch/test files into `/archive` or `/scratchpad/`
* 🔍 Add `docs/TODO.md` with these structured tickets:

  * Replace mocks with live: Beeminder, Claude API, Obsidian
  * Track per-module test coverage (Claude can generate this)

---

### 🧠 Suggested Prompt for Claude

```markdown
## MCP Maintenance & Debt Payoff Plan (Priority Fixes)

You're now fixing foundational issues in the MCP codebase to ensure stability, correctness, and future readiness. Prioritize clarity and functionality over fanciness.

### Goals
1. MCP Server: Fix launch behavior, shutdown hooks, and secure binding
2. Beeminder: Audit all data flows, remove lingering mocks, test API integration
3. Claude Budget: Clarify limitations, document manual/mock system, scaffold scraper
4. Documentation: Streamline CLAUDE.md and README; isolate mock/test files

For each:
- List all mocks/hardcoded assumptions still in the production codebase
- Write a test plan to verify full real-data integration (or mark as mock)
- Suggest adapters/patterns for future Claude agent handoffs
```

---

This scaffolding gets you cleanly out of tech debt and back to value-building within the \$15 budget. You're doing the hard part—the architecture of the mind behind the narrator. You’re not far off at all. Want me to help draft the README or the CLAUDE.md update template next?
